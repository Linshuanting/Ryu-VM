import json
from sortedcontainers import SortedList 

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

def tuple_key_to_str(data):
    new_dict = {}
    for k, v in data.items():
        # 若 k 是 tuple，就轉成字串
        new_key = tuple_to_str(k)

        # 若 v 也是 dict，就遞迴處理
        if isinstance(v, dict):
            new_dict[new_key] = tuple_key_to_str(v)
        else:
            new_dict[new_key] = v
    return new_dict

def tuple_to_str(data):
    if isinstance(data, tuple):
        return '-'.join(map(str, data))
    else:
        return data
    
def str_to_tuple(data):
    try:
        u, v = map(str, data.split('-'))  # 將字符串轉換為整數 tuple
        return (u, v)
    except ValueError as e:
        raise ValueError(f"Invalid data format for conversion to tuple: {data}") from e

def to_dict(d):
        if isinstance(d, dict):
            # 僅對值進行遞歸處理，保留 key 的原始類型
            return {to_dict(k): to_dict(v) for k, v in d.items()}
        elif isinstance(d, (SortedList, list)):
            # 對列表或排序列表的元素進行遞歸處理
            return [to_dict(v) for v in d]
        elif isinstance(d, tuple):
            # 如果需要兼容 JSON，這裡可以將 tuple 轉換為列表
            return tuple_to_str(d)
        elif isinstance(d, (int, float, str)):
            # 保留基本類型
            return d
        else:
            # 未知類型，記錄警告並直接返回字符串表示
            print(f"Unknown type encountered: {type(d)}, value: {d}")
            return str(d)