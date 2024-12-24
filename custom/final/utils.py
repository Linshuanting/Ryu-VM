import json

def print_json_in_file(file_path):
    """
    打印 JSON 文件内容为美观的格式。
    
    :param file_path: JSON 文件路径
    """
    try:
        # 打开并读取 JSON 文件
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 格式化打印 JSON 数据
        print(json.dumps(data, indent=4, ensure_ascii=False))
    except FileNotFoundError:
        print(f"Error: File not found at {file_path}")
    except json.JSONDecodeError as e:
        print(f"Error: Failed to decode JSON. {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

def print_json(data):
    print(json.dumps(data, indent=4, ensure_ascii=False))