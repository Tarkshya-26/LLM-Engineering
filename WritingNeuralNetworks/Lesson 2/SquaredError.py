import numpy as np

hours = np.array([1,2,3,5], dtype=float)

marks = np.array([20,40,60,80], dtype=float)

weight = 5.0

predictions = hours * weight

errors = marks - predictions
print(errors)

squared_errors = errors **2
print(squared_errors)

