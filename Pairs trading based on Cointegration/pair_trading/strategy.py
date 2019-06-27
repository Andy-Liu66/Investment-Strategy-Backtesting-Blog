import pandas as pd


class Strategy:
    '''
    next_bar - 訊號出現後何時進出場，0為出現後馬上執行交易，1為下一個價格執行交易，2...以此類推
    trade_on - 以甚麼價格進行交易
    initial_capital - 初始資金(後續分析中沒有使用到)
    tax_rate - 交易稅
    cost - 交易成本(率)
    '''
    
    def __init__(
        self, next_bar=1, trade_on='close',
        initial_capital = 1000000, tax_rate=0.003, cost=0.001425
    ):
        self.next_bar = next_bar
        self.trade_on = trade_on
        self.initial_capital = initial_capital
        self.tax_rate = tax_rate
        self.cost = cost
    
    # 以下__開頭者為內部使用function
    def __generate_signal(self, condition_list):
        signal = pd.Series([True] * len(condition_list[0]))

        # 回傳所有條件的交集(這裡只處理"且")
        # 其實在外部輸入condition時就可以處理and(&), or(|)的條件
        # 但若在外部寫則會較繁瑣，因此仍保留此function
        for condition in condition_list:
            signal = condition & signal
        return signal
    
    def __generate_position(self, buy_or_short='buy'):

        # 產生內部函數處理對沖比率
        def __define_position_size():
            # 依據信號出現時的index建立空的position_size
            position_size = pd.DataFrame(
                0,
                index=self.__position_index,
                columns=['stock_to_buy_position_size', 'stock_to_sellshort_position_size']
            )

            # 決定對沖比率
            for i in self.__position_index:
                current_stock_to_buy = self.stock_to_buy[self.trade_on][i]
                current_stock_to_sellshort = self.stock_to_sellshort[self.trade_on][i]
                # 使價格較高者部位為1，價格較低者部位則由高價除以低價並四捨五入
                if current_stock_to_buy >= current_stock_to_sellshort:
                    position_size.stock_to_buy_position_size[i] = 1
                    position_size.stock_to_sellshort_position_size[i] = round(
                        current_stock_to_buy/current_stock_to_sellshort
                    )
                else:
                    position_size.stock_to_buy_position_size[i] = round(
                        current_stock_to_sellshort/current_stock_to_buy
                    )
                    position_size.stock_to_sellshort_position_size[i] = 1
            
            # 上述作法同時考量進出場，但部位應只由進場決定
            # 部位為兩兩一組，前者為進場後者為出場，因此將後者的值改為前者
            for i in range(len(position_size)):
                # 使用try以避免index out of range
                try:
                    position_size.iloc[2*i + 1] = position_size.iloc[2*i]
                except:
                    pass
            # 以張為單位因此乘1000
            return position_size * 1000

        has_position = False
        positions = pd.Series(0, index=self.signal.index)
        if buy_or_short == 'buy':
            position = 1
        elif buy_or_short == 'short':
            position = -1

        # 若signal裡的condition_in出現進場訊號且沒有部位則進場
        # 若有部位且signal裡的condition_out出現出場訊號則平倉
        # 最外層的if用來避免進出場訊號同時出現(訊號會亂掉)
        # 此種寫法尚未考量加減碼，透過buy_or_short決定建倉方向
        for i in range(len(positions)):
            if self.signal.condition_in.iloc[i] != self.signal.condition_out.iloc[i]:
                if self.signal.condition_in.iloc[i] == True:
                    if not has_position:
                        positions.iloc[i] = position
                        has_position = True
                if self.signal.condition_out.iloc[i] == True:
                    if has_position:
                        positions.iloc[i] = -1*position
                        has_position = False

        # 儲存進出場信號出現時的index           
        self.__position_index = positions[positions != 0].index
        
        # __generate_position會在run中呼叫兩次
        # 因此透過以下方法來判斷position_size是否已建立，避免再次執行(不影響結果但可能影響速度)
        try:
            # 若未被呼叫則會進到except進行呼叫
            self.position_size != None
        except:
            if len(self.hedge_ratio) == 2 and type(self.hedge_ratio) == list:
                position_size = pd.DataFrame(
                    0,
                    index=self.__position_index,
                    columns=['stock_to_buy_position_size', 'stock_to_sellshort_position_size']
                )
                position_size.stock_to_buy_position_size = float(self.hedge_ratio[0]) * 1000
                position_size.stock_to_sellshort_position_size = float(self.hedge_ratio[1]) * 1000
                self.position_size = position_size
            else:
                self.position_size = __define_position_size()

        # 由於position_size只包含有進出場時的部位(index較少)
        # 因此乘上原先信號(0, 1, -1)時會有na出現，所以要fillna
        if buy_or_short == 'buy':
            positions = (self.position_size.stock_to_buy_position_size * positions).fillna(0)
        elif buy_or_short == 'short':
            positions = (self.position_size.stock_to_sellshort_position_size * positions).fillna(0)

        # 上述只標記進出場點位(未考量持倉狀況)且未考量買賣時機
        # 透過cumsum決定出部位狀況，例如：0,1,0,0,-1代表第二天出現進場訊號第五天出現出場訊號
        # cumsum後則變為0,1,1,1,0，意味在第二~四天時持有多頭部位
        # 接著透過shift決定出實際部位持有時間點，因為訊號出現後通常用下一資料點進出場(可由next_bar調整)
        # shift(1)後則變為na,0,1,1,1,0，則變為在第三~五天時持有多頭部位
        positions = positions.cumsum().shift(periods=self.next_bar)

        # 若最後一期有留倉則強制平倉
        if positions.iloc[-1] != 0:
            positions.iloc[-1] = 0
        return positions
    
    def __generate_trade_table(self, buy_or_short='buy'):

        # 持倉狀況(position)→進場後為1(多)或-1(空)，空手為0。
        # 上述例子：na,0,1,1,1,0，為第三~五天時持有多頭部位
        if buy_or_short == 'buy':
            position =  self.signal.stock_to_buy_position
            stock_price = self.stock_to_buy[self.trade_on]
        elif buy_or_short == 'short':
            position =  self.signal.stock_to_sellshort_position
            stock_price = self.stock_to_sellshort[self.trade_on]
        
        # 持有部位大小乘上股價與後即為持有部位價值(holdings)
        holdings = position * stock_price
        
        # 暫存日期(用stock_to_sellshort.date也一樣，因為已經preprocess後才送入class)
        date = self.stock_to_buy.date

        # 進出場點位(entry_exit_points)→多頭部位進場為1出場為-1，空頭部位進場為-1出場為1
        # 透過diff(差分)計算，以上述na,0,1,1,1,0例子而言，取diff()後為na,na,1,0,0,-1(第三天進場第六天平倉)
        entry_exit_points = position.diff()

        # 紀錄現金部位，概念相對複雜，解釋過程在help資料夾中
        cash = self.initial_capital - (entry_exit_points * stock_price).cumsum()

        # 紀錄部位總價值(浮動，因為有考量holdings)，現金+股票部位
        total_value = cash + holdings

        # 浮動權益不含初始資金
        cumulative_profit = total_value - self.initial_capital

        trade_table = pd.DataFrame([])
        trade_table['date'] = date
        trade_table[self.trade_on + '_price'] = stock_price
        trade_table['holdings'] = holdings
        trade_table['entry_exit_points'] = entry_exit_points
        trade_table['cash'] = cash
        trade_table['total_value'] = total_value
        trade_table['cumulative_profit'] = cumulative_profit
        return trade_table

    def run(
        self, stock_to_buy, stock_to_sellshort,
        condition_in, condition_out,
        hedge_ratio='auto'
    ):
        '''
        stock_to_buy - condition_in成立時欲做多的股票
        stock_to_sellshort - condition_in成立時欲放空的股票
        condition_in - 進場訊號
        condition_out - 出場訊號
        hedge_ratio - 對沖比率，預設為auto，亦即將兩兩欲交易的價格(trade_on)進行比較，
                      將價格較高者部位設為1，價格較低者部位則由高價除以低價並四捨五入
                      也可以輸入list如：[2, 1]，將會以2:1的部位進行交易(stock_to_buy : stock_to_sellshort)
        '''
        self.stock_to_buy = stock_to_buy
        self.stock_to_sellshort = stock_to_sellshort
        self.condition_in = condition_in
        self.condition_out = condition_out
        self.hedge_ratio = hedge_ratio

        # 建立訊號
        self.signal = pd.DataFrame()
        self.signal['condition_in'] = self.__generate_signal(condition_in)
        self.signal['condition_out'] = self.__generate_signal(condition_out)

        # 建立部位
        self.signal['stock_to_buy_position'] = self.__generate_position(buy_or_short='buy')
        self.signal['stock_to_sellshort_position'] = self.__generate_position(buy_or_short='short')

        # 儲存結果
        self.stock_to_buy_trade_table = self.__generate_trade_table(buy_or_short='buy')
        self.stock_to_sellshort_trade_table = self.__generate_trade_table(buy_or_short='short')