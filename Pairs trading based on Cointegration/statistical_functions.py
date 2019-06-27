import pandas as pd
import numpy as np
from arch.unitroot import ADF
from scipy import odr


def preprocess(stock_1, stock_2):
    stock_1 = stock_1.copy()
    stock_2 = stock_2.copy()
    stock_1.dropna(inplace=True)
    stock_2.dropna(inplace=True)
    date_index = stock_1.merge(stock_2, on='date')['date']
    stock_1 = stock_1[stock_1.date.isin(date_index)]
    stock_1.reset_index(inplace=True, drop=True)
    stock_1.sort_values(by='date', inplace=True)
    stock_2 = stock_2[stock_2.date.isin(date_index)]
    stock_2.reset_index(inplace=True, drop=True)
    stock_2.sort_values(by='date', inplace=True)
    return stock_1, stock_2


def test_is_I1(price, alpha=0.05):
    adf_price = ADF(price)
    adf_return = ADF(np.diff(price))
    adf_price_is_pass = adf_price.pvalue < alpha
    adf_return_is_pass = adf_return.pvalue < alpha
    if (adf_price_is_pass == False) and (adf_return_is_pass == True):
        is_I1 = True
    else:
        is_I1 = False
    
    return is_I1


def TLS_regresssion(stock_1, stock_2):
    def f(B, x):
        '''Linear function y = m*x + b'''
        # B is a vector of the parameters.
        # x is an array of the current x values.
        # x is in the same format as the x passed to Data or RealData.
        # Return an array in the same format as y passed to Data or RealData.
        return B[0]*x + B[1]

    linear_model = odr.Model(f)
    used_data = odr.Data(stock_1, stock_2)
    TLS_regression_model = odr.ODR(used_data, linear_model, beta0=[1., 2.])
    result = TLS_regression_model.run()
    return result


def test_is_tradable(stock_1, stock_2, alpha=0.05):
    stock_1 = np.log(stock_1.values)
    stock_2 = np.log(stock_2.values)
    if (test_is_I1(stock_1) == True) and (test_is_I1(stock_2) == True):
        TLS_result = TLS_regresssion(stock_1, stock_2)
        residual = stock_2 - TLS_result.beta[1] - TLS_result.beta[0]*stock_1
        residual_ADF_test_result = ADF(residual, trend="nc")
        if residual_ADF_test_result.pvalue >= alpha:
            pass
        else:
            trade_parameter = pd.DataFrame([[
                TLS_result.beta[0], TLS_result.beta[1],
                np.std(residual), residual_ADF_test_result.stat
            ]], columns=[
                'hedge_ratio', 'intercept',
                'sigma', 'ADF_statistic'
            ])
            return trade_parameter
    else:
        pass