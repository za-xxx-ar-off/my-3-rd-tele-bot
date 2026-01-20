# простой словарь для хранения прогресса по chat_id
data = {}

def init():
    pass  # здесь можно подключение к настоящей БД

def get(chat_id):
    return data.get(chat_id, 1)  # старт с 1

def set(chat_id, row):
    data[chat_id] = row

def clear(chat_id):
    if chat_id in data:
        del data[chat_id]
