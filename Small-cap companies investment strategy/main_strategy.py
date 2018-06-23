import pandas as pd
import numpy as np

class strategy:

    def __init__(self, data, data_year, data_date, first_date_each_year):
        self.data = data
        self.data_year = data_year
        self.data_date = data_date
        self.first_date_each_year = first_date_each_year

    def calculate_return(self, num_selected = 10, by = "MV", 
                         ascending = True, least_volume = 10, trade_mode = "A",
                         weight_mode = "equal", initial_capital = 100, transaction_cost = 0.00585):
        #empty dataframe to collect final result
        self.selected_data = pd.DataFrame([])
        for i in range(len(self.first_date_each_year)):
            #entry point
            date_in = self.first_date_each_year[i]
            #exit point, a year after entry point (use the latest date of data when dealing with latest year)
            try:
                date_out = self.first_date_each_year[i + 1]
            except:
                date_out = self.data_date.iloc[-1, :]["Date"]

            #deal with entry trade 
            #selected companies need to possess trading data on appointed date
            temp_data_in = self.data[self.data.Date == date_in]
            #also need to meet the requirement of least trading volume(in case of liquidity risk)
            temp_data_in = temp_data_in[temp_data_in.Volume >= least_volume]
            #if ascending == true, data will be sorted by appointed column in ascending order(the smaller value the closer to front), vice versa
            temp_data_in = temp_data_in.sort_values(by = by, ascending = ascending).reset_index(drop = True)
            #according to condition of "ascending", select the top "num_selected" rows of data,
            #e.g. if ascending == True, num_selected = 10, by = "MV", it will select the smallest 10 rows of data according to MV value
            temp_data_in = temp_data_in.iloc[0:num_selected, :]
            
            #deal with exit trade
            #empty dataframe to collect temp result of exit trade
            temp_data_out = pd.DataFrame([])
            for code in temp_data_in.Code:
                #find the company included in the entry trade above
                temp_company = self.data[self.data.Code == code]
                #find the possible exit day according to entry point(later than default exit point, a year after entry point)
                temp_date_out = pd.DataFrame(temp_company.Date - date_out).Date.apply(lambda x : x.days)
                try:
                    #find the closest exit point according to default exit point
                    temp_date_out = temp_company.Date[temp_date_out[temp_date_out >= 0].idxmin()]
                    temp_result_out = temp_company[temp_company.Date == temp_date_out]
                    #change the columns' name of exit point
                    temp_result_out.columns = (self.data.columns + "_out")
                    #then check for the requirement of trade volume
                    if temp_result_out["Volume_out"].values < least_volume:
                        #in trade mode "A", set exit price = 0,
                        #the strictest condition, because we maybe unable to sell at such a low liquidity, it might means zeros market value at that point
                        if trade_mode == "A":
                            temp_result_out = pd.DataFrame([[0] * len(self.data.columns)], columns = (self.data.columns + "_out"))
                        #in trade mode "B", set exit price = entry price,
                        #it means zero return in this stock during the trade, it may undervalue or overvalue depends on different conditions
                        if trade_mode == "B":
                            temp_result_out = temp_data_in[temp_data_in.Code == code]
                            temp_result_out.columns = (self.data.columns + "_out")
                        #in trade mode "C", set exit price = price at exit point(regardless of low liquidity),
                        #although that company might has a price on exit point, but we maybe unable to sell at such a low liquidity
                        if trade_mode == "C":
                            temp_result_out = temp_result_out      
                #if the company was unlisted, then for loop would jump to except, set exit price = 0
                except:
                    temp_result_out = pd.DataFrame([[0] * len(self.data.columns)], columns = (self.data.columns + "_out"))
                #combine temp result of exit trade
                temp_data_out = pd.concat([temp_data_out, temp_result_out], axis = 0)
                temp_data_out.reset_index(inplace = True, drop = True)
            #combine temp result of entry trade and exit trade
            temp_selected_data = pd.concat([temp_data_in,  temp_data_out], axis = 1)
            #collect final result
            self.selected_data = pd.concat([self.selected_data, temp_selected_data], axis = 0)

        #calculate return
        self.initial_capital = initial_capital
        #assume there is a fund trading different portfolio year by year according to the trades in "self.selected_data" above
        #as a result, we need to calculate the return in a cumulative way to investigate the change of value compare to the start
        for date in self.selected_data.Date.unique():
            temp = self.selected_data[self.selected_data.Date == date]
            #the weight of portfolio will be equally weighted
            if weight_mode == "equal":
                weight_array = np.array([1/len(temp)] * len(temp))
            #the weight of portfolio will be weighted according to companies' market value
            if weight_mode == "MVbased":
                weight_array = np.array(temp.MV / temp.MV.sum())
            #calculate return for each company in the portfolio
            temp_return =  ((temp.Close_out - temp.Close) / temp.Close + 1 - transaction_cost)
            #allocation of capital, it will be rebalance year by year
            capital_allocation = self.initial_capital * weight_array
            #calculate remain capital year by year
            self.initial_capital = np.dot(capital_allocation, temp_return)
        #calculate total return
        self_return = (self.initial_capital / initial_capital) -1
        return [self.initial_capital, self_return]


