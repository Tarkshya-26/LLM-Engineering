import numpy as np

hours = np.array([1,2,3,4])

print(hours.dtype) # -> Results to int64

hours = np.array([1,2,3,4.5])
print(hours.dtype) # -> Results to float64
