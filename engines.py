import torch

engines = torch.backends.quantized.supported_engines
print(engines)
