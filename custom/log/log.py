import logging
import os

class MyLog:
    def __init__(self, logger_name, log_file_path, log_level=logging.INFO, mode='w'):
        """
        初始化 MyLog 類

        :param logger_name: 日誌記錄器的名稱
        :param log_file_path: 日誌文件的路徑（可以包含 ~ 符號）
        :param log_level: 日誌級別，默認為 logging.INFO
        :param mode: 文件打開模式，默認為 'w' 覆寫模式
        """
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(log_level)

        # 展開用戶主目錄符號（~）
        log_file_path = os.path.expanduser(log_file_path)

        # 創建文件處理器
        file_handler = logging.FileHandler(log_file_path, mode=mode)
        
        # 設置日誌格式
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)

        # 添加處理器到記錄器
        self.logger.addHandler(file_handler)


    def get_logger(self):
        """
        返回配置好的日誌記錄器

        :return: 日誌記錄器對象
        """
        return self.logger

# 使用範例
if __name__ == "__main__":
    my_log = MyLog(logger_name="MyAppLogger", log_file_path="custom/myapp.log")
    logger = my_log.get_logger()

    # 測試日誌輸出
    logger.info("This is an info message.")
    logger.error("This is an error message.")
