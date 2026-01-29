"""
Валидатор для проверки логичности динамических коэффициентов
"""

class OddsValidator:
    def validate(self, match_odds):
        """
        Проверка логичности коэффициентов

        ПРАВИЛА:
        1. Для отрицательных фор (фаворит): чем больше фора, тем ВЫШЕ коэффициент
           F(-0.5) < F(-1.5) < F(-2.5)

        2. Для положительных фор (аутсайдер): чем больше фора, тем НИЖЕ коэффициент
           F(+0.5) > F(+1.5) > F(+2.5)
        """
        warnings = []
        handicaps = match_odds.get('handicaps', {})

        # Проверка Team1
        if 'Team1' in handicaps:
            team1 = handicaps['Team1']
            team_name = team1.get('name', 'Team1')

            # Извлекаем форы
            foras = []
            for key, value in team1.items():
                if key.startswith('F(') and value is not None:
                    handicap_val = self._extract_handicap_value(key)
                    foras.append((handicap_val, key, value))

            # Сортируем по значению форы
            foras.sort(key=lambda x: x[0])

            # Проверяем логику
            for i in range(len(foras) - 1):
                current_val, current_name, current_odd = foras[i]
                next_val, next_name, next_odd = foras[i + 1]

                # Определяем правило в зависимости от знака
                if current_val < 0 and next_val < 0:
                    # Отрицательные форы: коэффициент должен расти
                    # F(-2.5) > F(-1.5) > F(-0.5)
                    if current_odd < next_odd:
                        warnings.append(
                            f"⚠️  {team_name}: {current_name} ({current_odd:.2f}) должна быть >= {next_name} ({next_odd:.2f})"
                        )
                elif current_val > 0 and next_val > 0:
                    # Положительные форы: коэффициент должен падать
                    # F(+0.5) > F(+1.5) > F(+2.5)
                    if current_odd < next_odd:
                        warnings.append(
                            f"⚠️  {team_name}: {current_name} ({current_odd:.2f}) должна быть >= {next_name} ({next_odd:.2f})"
                        )

        # Проверка Team2
        if 'Team2' in handicaps:
            team2 = handicaps['Team2']
            team_name = team2.get('name', 'Team2')

            # Извлекаем форы
            foras = []
            for key, value in team2.items():
                if key.startswith('F(') and value is not None:
                    handicap_val = self._extract_handicap_value(key)
                    foras.append((handicap_val, key, value))

            # Сортируем по значению форы
            foras.sort(key=lambda x: x[0])

            # Проверяем логику
            for i in range(len(foras) - 1):
                current_val, current_name, current_odd = foras[i]
                next_val, next_name, next_odd = foras[i + 1]

                # Определяем правило в зависимости от знака
                if current_val < 0 and next_val < 0:
                    # Отрицательные форы: коэффициент должен расти
                    if current_odd < next_odd:
                        warnings.append(
                            f"⚠️  {team_name}: {current_name} ({current_odd:.2f}) должна быть >= {next_name} ({next_odd:.2f})"
                        )
                elif current_val > 0 and next_val > 0:
                    # Положительные форы: коэффициент должен падать
                    if current_odd < next_odd:
                        warnings.append(
                            f"⚠️  {team_name}: {current_name} ({current_odd:.2f}) должна быть >= {next_name} ({next_odd:.2f})"
                        )

        # Проверка тоталов
        totals = match_odds.get('totals', {})
        for line in [8.5, 9.5, 10.5, 11.5]:
            over_key = f'Over_{line}'
            under_key = f'Under_{line}'

            if over_key in totals and under_key in totals:
                over_odd = totals[over_key]
                under_odd = totals[under_key]

                if over_odd and under_odd:
                    # Проверяем, что сумма обратных вероятностей близка к 1 + маржа
                    sum_probs = (1/over_odd) + (1/under_odd)
                    if not (1.05 <= sum_probs <= 1.15):  # Допустимый диапазон с маржой 8.5%
                        warnings.append(
                            f"⚠️  Тотал {line}: сумма вероятностей {sum_probs:.3f} (норма 1.08-1.10)"
                        )

        return warnings

    def _extract_handicap_value(self, handicap_str):
        """
        Извлекает числовое значение форы из строки типа 'F(-1.5)' или 'F(+2.5)'
        """
        import re
        match = re.search(r'([+-]?\d+\.?\d*)', handicap_str)
        if match:
            return float(match.group(1))
        return 0.0