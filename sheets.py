# пример тестов
tests = [
    ("https://via.placeholder.com/150", "Вопрос 1?"),
    (None, "Вопрос 2?"),
    ("https://via.placeholder.com/150", "Вопрос 3?")
]

# пользователи и их колонки (заглушка)
user_columns = {}

def total_rows():
    return len(tests)

def get_test(row):
    if row-1 < len(tests):
        return tests[row-1]
    return None, None

def get_or_create_user_column(user):
    if user not in user_columns:
        user_columns[user] = len(user_columns)+1
    return user_columns[user]

def save_answer(row, col, answer):
    print(f"Сохраняем ответ: row={row}, col={col}, answer={answer}")
