import torch

path = "sourya_module/image_embeddings.pt"

data = torch.load(path, map_location="cpu", weights_only=True)

print("Object type:", type(data))
print("Number of embeddings:", len(data))
print("\nFirst five entries:")

for i, (key, value) in enumerate(data.items()):
    if i == 5:
        break
    print(key, type(value), getattr(value, "shape", None))

shapes = set(
    tuple(value.shape) for value in data.values()
    if isinstance(value, torch.Tensor)
)

print("\nUnique embedding shapes:", shapes)
print("Total tensor embeddings:", sum(
    isinstance(value, torch.Tensor) for value in data.values()
))
