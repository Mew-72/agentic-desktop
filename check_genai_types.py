import google.genai.types as types
dir_types = dir(types)
print(f"CodeExecution Tool: {'ToolCodeExecution' in dir_types or 'CodeExecution' in dir_types}")
print(f"ThinkingConfig: {'ThinkingConfig' in dir_types}")
print([t for t in dir_types if 'think' in t.lower() or 'code' in t.lower()])
from pprint import pprint
print("Dir of Tool:")
pprint(dir(types.Tool))
