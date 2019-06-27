import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
plt.style.use('seaborn')

class Analysis:
    '''
    strategy - 輸入欲分析的策略(策略物件中含有交易表格，送入Analysis物件進行分析)
    '''
    
    def __init__(self, strategy):
        self.strategy = strategy
        self.stock_to_buy_trade_table = self.strategy.stock_to_buy_trade_table
        self.stock_to_sellshort_trade_table = self.strategy.stock_to_sellshort_trade_table
    
    def __parse_trade_result(self, buy_or_short='buy'):
        # 找出進出場的index
        if buy_or_short == 'buy':
            direction = 1
            trade_table = self.stock_to_buy_trade_table.reset_index(drop=True)
        elif buy_or_short == 'short':
            direction = -1
            trade_table = self.stock_to_sellshort_trade_table.reset_index(drop=True)
        entry_exit_index = pd.DataFrame({
            'entry': trade_table[trade_table.entry_exit_points*direction > 0].index,
            'exit': trade_table[trade_table.entry_exit_points*direction < 0].index
        }) 

        # 紀錄交易結果相關資訊
        trade_result = pd.DataFrame([])
        for i in range(len(entry_exit_index)):
            current_index = entry_exit_index.iloc[i]
            temp_entry_index, temp_exit_index = current_index.entry, current_index.exit
            temp_table = trade_table.iloc[temp_entry_index: temp_exit_index+1]
            temp_table = temp_table.copy()

            # 紀錄進出場日期與持有時間
            entry_date = temp_table.date.iloc[0]
            exit_date = temp_table.date.iloc[-1]
            holding_date = (exit_date - entry_date).days

            # 記錄進出場價格及部位大小
            # 第2個column為價格資料，因為可能是用其他價格進行交易例如：open, high等，因此用index的方式呼叫
            entry_price = temp_table.iloc[0, 1]
            exit_price = temp_table.iloc[-1, 1]
            position_size = temp_table.entry_exit_points.iloc[0]

            # 找出MFE, MAE
            # 扣掉累加的報酬才能找出發生在當筆交易的損益狀況
            temp_table['potential_profit'] = temp_table.cumulative_profit - temp_table.cumulative_profit.iloc[0]
            maximum_favorable_excursion = temp_table['potential_profit'].max()
            maximum_adverse_excursion = temp_table['potential_profit'].min()

            # 紀錄報酬
            gross_profit = temp_table['potential_profit'].iloc[-1]
            gross_return = gross_profit/abs(temp_table.holdings.iloc[0])
            trade_cost = (
                # 手續費(進出場接收)
                entry_price * abs(position_size) * self.strategy.cost +
                exit_price * abs(position_size) * self.strategy.cost +
                # 交易稅(出場收)
                exit_price * abs(position_size) * self.strategy.tax_rate
                )
            net_profit = gross_profit - trade_cost
            net_return = net_profit/abs(temp_table.holdings.iloc[0])

            # 將資料整理成dataframe
            temp_result = pd.DataFrame({
                'entry_date': entry_date,
                'exit_date': exit_date,
                'holding_date': holding_date,
                'position_size': position_size,
                'entry_price': entry_price,
                'exit_price': exit_price,
                'gross_profit': gross_profit,
                'gross_return': gross_return,
                'trade_cost': trade_cost,
                'net_profit': net_profit,
                'net_return': net_return,
                # 考量手續費後的MFE, MAE
                'maximum_favorable_excursion': maximum_favorable_excursion - trade_cost,
                'maximum_adverse_excursion': maximum_adverse_excursion - trade_cost
            }, columns=[
                # 需指定columns否則順序會跑掉
                'entry_date',
                'exit_date',
                'holding_date',
                'position_size',
                'entry_price',
                'exit_price',
                'gross_profit',
                'gross_return',
                'trade_cost',
                'net_profit',
                'net_return',
                'maximum_favorable_excursion',
                'maximum_adverse_excursion'
            ], index=[i])

            # 合併dataframe
            trade_result = pd.concat([trade_result, temp_result])
        return trade_result
    
    def run(self):
        '''
        執行分析
        '''
        # 做多交易結果
        self.stock_to_buy_trade_result = self.__parse_trade_result(buy_or_short='buy')

        # 做空交易結果
        self.stock_to_sellshort_trade_result = self.__parse_trade_result(buy_or_short='short')
        
        # 總結果(做多與做空為一個配對，只儲存以下分析需要用到的變數)
        total_trade_result = pd.DataFrame([])
        total_trade_result['net_profit'] = (
            self.stock_to_buy_trade_result.net_profit +
            self.stock_to_sellshort_trade_result.net_profit
        )

        total_trade_result['net_return'] = (
            # 報酬率用相加的有點奇怪(但目前仍使用相加)
            self.stock_to_buy_trade_result.net_return +
            self.stock_to_sellshort_trade_result.net_return
        )

        total_trade_result['holding_date'] = (
            self.stock_to_buy_trade_result.holding_date +
            self.stock_to_sellshort_trade_result.holding_date
        )/2

        total_trade_result['maximum_favorable_excursion'] = (
            self.stock_to_buy_trade_result.maximum_favorable_excursion +
            self.stock_to_sellshort_trade_result.maximum_favorable_excursion
        )

        total_trade_result['maximum_adverse_excursion'] = (
            self.stock_to_buy_trade_result.maximum_adverse_excursion +
            self.stock_to_sellshort_trade_result.maximum_adverse_excursion
        )
        self.total_trade_result = total_trade_result
    
    def summary(self, select_result='total'):
        '''
        total - 顯示總交易結果
        buy - 顯示做多交易結果
        sellshort - 顯示做空交易結果
        '''
        
        if select_result == 'buy':
            trade_result = self.stock_to_buy_trade_result
        elif select_result == 'sellshort':
            trade_result = self.stock_to_sellshort_trade_result
        elif select_result == 'total':
            trade_result = self.total_trade_result
        
        # 總獲利金額
        total_profit = trade_result.net_profit.sum()
        
        # 平均報酬
        average_return = trade_result.net_return.mean()
        
        # 勝率
        total_trade_number = len(trade_result)
        win_trade_num = sum(trade_result.net_profit > 0)
        winning_rate = win_trade_num/total_trade_number
        
        # 最大獲利回撤
        accumulate_profit = trade_result.net_profit.cumsum()
        max_drowdown = max(np.maximum.accumulate(accumulate_profit) - accumulate_profit)
        
        # 平均持有天數
        average_holding_days = trade_result.holding_date.mean()
        
        summary = pd.DataFrame({
            'total_profit': total_profit,
            'average_return': average_return,
            'winning_rate': winning_rate,
            'max_drowdown': max_drowdown,
            'average_holding_days': average_holding_days,
            'total_trade_number': total_trade_number
        }, columns=[
            'total_profit',
            'average_return',
            'winning_rate',
            'max_drowdown',
            'average_holding_days',
            'total_trade_number'
        ], index=[0])
        
        summary = summary.apply(lambda x: round(x, 4))
        return summary

    def plot_equity_curve(self, select_result='total', figsize=(16, 8)):
        '''
        total - 顯示總交易結果
        buy - 顯示做多交易結果
        sellshort - 顯示做空交易結果
        '''
        
        if select_result == 'buy':
            trade_result = self.stock_to_buy_trade_result
        elif select_result == 'sellshort':
            trade_result = self.stock_to_sellshort_trade_result
        elif select_result == 'total':
            trade_result = self.total_trade_result
        else:
            raise Exception('Wrong input of select_result!')
        
        # 累積獲利
        accumulate_profit = trade_result.net_profit.cumsum()
        
        # 找出創新高的index(要畫綠點)
        new_highest_index = []
        for i in range(len(accumulate_profit)):
            current_accumulate_profit = accumulate_profit.iloc[i]
            if i == 0:
                new_highest = accumulate_profit.iloc[i]
            if (current_accumulate_profit > new_highest) and (current_accumulate_profit > 0):
                new_highest = current_accumulate_profit
                new_highest_index.append(i)
        
        plt.figure(figsize=figsize)
        # 權益曲線
        plt.plot(accumulate_profit, c='black')
        # 創新高的點
        plt.scatter(new_highest_index,
                    accumulate_profit[new_highest_index], c='#02ff0f', s=70)
        plt.title('Equity Curve - {}'.format(select_result), size=20)
        plt.xlabel('Trade Number', size=15)
        plt.ylabel('NTD', size=15)
        plt.xticks(size=13)
        plt.yticks(size=13);
    
    def plot_profit_and_loss_per_trade(self, select_result='total', figsize=(16, 8)):
        '''
        total - 顯示總交易結果
        buy - 顯示做多交易結果
        sellshort - 顯示做空交易結果
        '''

        if select_result == 'buy':
            trade_result = self.stock_to_buy_trade_result
        elif select_result == 'sellshort':
            trade_result = self.stock_to_sellshort_trade_result
        elif select_result == 'total':
            trade_result = self.total_trade_result
        else:
            raise Exception('Wrong input of select_result!')
        
        index = trade_result.index
        plt.figure(figsize=figsize)
        # 實際獲利與虧損
        plt.bar(trade_result.net_profit[trade_result.net_profit > 0].index,
                trade_result.net_profit[trade_result.net_profit > 0],
                label='Profit', color='red')
        plt.bar(trade_result.net_profit[trade_result.net_profit < 0].index,
                trade_result.net_profit[trade_result.net_profit < 0],
                label='Loss', color='green')
        # 潛在獲利與虧損
        plt.bar(trade_result.index,
                trade_result.maximum_favorable_excursion,
                color='red', alpha=0.2, label='Possible Profit')
        plt.bar(trade_result.index,
                trade_result.maximum_adverse_excursion,
                color='green', alpha=0.2, label='Possible Loss')
        
        plt.legend(fontsize=13)
        plt.title('Profit and Loss per trade - {}'.format(select_result), size=20)
        plt.xlabel('Trade Number', size=15)
        plt.ylabel('NTD', size=15)
        plt.xticks(size=13)
        plt.yticks(size=13);