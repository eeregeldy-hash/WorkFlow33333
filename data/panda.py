import pandas as pd
from pathlib import Path
import os


def combine_e_files():
    # Автоматически находит папку, где лежит ваш скрипт (предполагая,
    # что E-файлы лежат рядом со скриптом, а не в подпапке 'data')
    input_folder = Path(__file__).parent

    # Имя итогового файла
    output_file = "historical.csv"

    # !!! Только нужные вам столбцы !!!
    required_columns = ['Div', 'HomeTeam', 'AwayTeam', 'HC', 'AC']

    # Явно указываем типы данных как текст для надежности чтения
    dtype_mapping = {col: object for col in required_columns}

    # Список для сбора всех данных
    all_dfs = []

    print(f"Поиск и обработка файлов в папке: {input_folder.resolve()}\n")

    for i in range(1, 11):
        filename = f"E{i}.csv"
        file_path = input_folder / filename

        if not file_path.exists():
            # Если файлы в папке 'data', раскомментируйте строку ниже:
            # file_path = input_folder / 'data' / filename
            if not file_path.exists():
                print(f"✗ Файл не найден: {filename}")
                continue

        try:
            # Читаем файл, используя явные типы данных и только нужные столбцы
            df = pd.read_csv(file_path, low_memory=False, dtype=dtype_mapping, usecols=required_columns)

            # Просто добавляем метку откуда данные
            df['source_file'] = f"E{i}"

            all_dfs.append(df)

            print(f"✓ {filename:8} → {len(df):6,} строк, "
                  f"найдено столбцов: {len(df.columns) - 1}")  # -1 потому что source_file это служебный

        except Exception as e:
            print(f"✗ Ошибка при чтении {filename}: {e}")
            continue

    if not all_dfs:
        print("\nНе удалось прочитать ни одного подходящего файла.")
        return

    # Объединяем всё в одну таблицу
    final_df = pd.concat(all_dfs, ignore_index=True)

    # Сохраняем
    final_df.to_csv(output_file, index=False, encoding='utf-8-sig')

    print("\n" + "=" * 60)
    print(f"Готово!")
    print(f"Объединено файлов: {len(all_dfs)}")
    print(f"Всего строк:     {len(final_df):,}")
    print(f"Сохранено в:     {output_file}")
    print("=" * 60)
    print("Столбцы в итоговом файле:")
    print(list(final_df.columns))


# Запуск
if __name__ == "__main__":
    combine_e_files()
