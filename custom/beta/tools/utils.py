import json, os
from sortedcontainers import SortedList 

def initialize_file(file_name):
    """
    初始化 JSON 檔案（若存在則清空）。
    
    :param file_name: 檔案名稱
    """
    file_name = os.path.expanduser(file_name)
    with open(file_name, 'w', encoding='utf-8') as file:
        json.dump([], file, ensure_ascii=False, indent=4)
    print(f"檔案 {file_name} 已初始化（清空內容）。")

def append_to_json(file_name, data):
    """
    將資料新增到 JSON 檔案的尾部。
    
    :param file_name: 檔案名稱
    :param data: 要新增的資料（字典格式）
    """
    try:
        # 讀取現有內容
        file_name = os.path.expanduser(file_name)
        if os.path.exists(file_name):
            with open(file_name, 'r', encoding='utf-8') as file:
                existing_data = json.load(file)
        else:
            existing_data = []

        # 新增新資料
        existing_data.append(data)

        # 寫回檔案
        with open(file_name, 'w', encoding='utf-8') as file:
            json.dump(existing_data, file, ensure_ascii=False, indent=4)

        print(f"資料已新增到 {file_name}")
    except Exception as e:
        print(f"新增資料時發生錯誤: {e}")

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

def print_dict(d, indent=0):
    """
    递归打印字典（支持嵌套字典、列表、元组）
    :param d: 需要打印的字典
    :param indent: 当前缩进层级
    """
    if not isinstance(d, dict):
        print("错误：输入的不是字典！")
        return

    for key, value in d.items():
        # 打印键
        print(" " * indent + f"{key}: ", end="")

        # 处理不同类型的值
        if isinstance(value, dict):  # 如果值是字典，递归调用
            print()  # 换行
            pretty_print_dict(value, indent + 4)
        elif isinstance(value, list):  # 处理列表
            print("[")
            for item in value:
                if isinstance(item, dict):
                    pretty_print_dict(item, indent + 4)
                else:
                    print(" " * (indent + 4) + str(item))
            print(" " * indent + "]")
        elif isinstance(value, tuple):  # 处理元组
            print("(" + ", ".join(str(i) for i in value) + ")")
        else:  # 其他基本类型
            print(value)

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
        elif d is None:
            return "None"
        else:
            # 未知類型，記錄警告並直接返回字符串表示
            print(f"Unknown type encountered: {type(d)}, value: {d}")
            return str(d)
        

