# src/calculator.py

import numpy as np
import pandas as pd

from src.bookmaker_grid import normalize_odds_pair, normalize_odds_triplet
from src.config import CONFIG


class CornerOddsCalculator:
    def __init__(self, margin=None, n_simulations=None):
        self.margin = CONFIG["MARGIN"] if margin is None else float(margin)
        self.n_simulations = CONFIG["N_SIMULATIONS"] if n_simulations is None else int(n_simulations)

        # cache профилей соперников из historical_df
        self._profiles_cache_df_id = None
        self._profiles_cache = None

    # ==================================================
    # PUBLIC
    # ==================================================
    def calculate_match_odds(self, historical_df, home_team, away_team, team_strength=None, form_df=None):
        if team_strength is None:
            team_strength = {}

        (
            lambda_home,
            lambda_away,
            base_lambda_home,
            base_lambda_away,
            s_home,
            s_away,
            ratio,
            form_home,
            form_away,
            anchor_scale,
            anchor_line
        ) = self._calculate_lambdas(
            historical_df, home_team, away_team, team_strength, form_df=form_df
        )

        favorite = self._determine_favorite(lambda_home, lambda_away)

        home_corners, away_corners, diff, total = self._monte_carlo_simulation(lambda_home, lambda_away)

        # 1X2 (на угловые)
        odds_1x2 = self._calculate_1x2(diff)

        # форы/тоталы/ит
        handicaps = self._calculate_handicaps_fixed_sides(diff)
        totals = self._calculate_totals(total)
        ind_home = self._calculate_individual_totals(home_corners)
        ind_away = self._calculate_individual_totals(away_corners)

        return {
            "lambda_home": float(lambda_home),
            "lambda_away": float(lambda_away),
            "expected_total": float(lambda_home + lambda_away),
            "favorite": favorite,

            # debug strength
            "base_lambda_home": float(base_lambda_home),
            "base_lambda_away": float(base_lambda_away),
            "strength_home": float(s_home),
            "strength_away": float(s_away),
            "strength_ratio": float(ratio),

            # debug form
            "form_home": float(form_home),
            "form_away": float(form_away),

            # debug anchor
            "anchor_line": anchor_line,
            "anchor_scale": float(anchor_scale),

            "odds_1x2": odds_1x2,
            "handicaps": handicaps,
            "totals": totals,
            "individual_home": ind_home,
            "individual_away": ind_away,
        }

    # ==================================================
    # PROFILES (из historical_df)
    # ==================================================
    def _build_corner_profiles(self, historical_df: pd.DataFrame):
        """
        profiles[team] = {
          for_avg:     сколько команда обычно подает угловых
          against_avg: сколько команда обычно допускает угловых
        }
        """
        df = historical_df
        teams = pd.unique(df[["HomeTeam", "AwayTeam"]].values.ravel("K"))

        profiles = {}
        for t in teams:
            t = str(t).strip()
            if not t or t.lower() == "nan":
                continue

            home_rows = df[df["HomeTeam"] == t]
            away_rows = df[df["AwayTeam"] == t]

            for_vals = []
            against_vals = []

            # for (угловые команды)
            for_vals.extend(home_rows["HC"].dropna().astype(float).tolist())
            for_vals.extend(away_rows["AC"].dropna().astype(float).tolist())

            # against (угловые соперника против команды)
            against_vals.extend(home_rows["AC"].dropna().astype(float).tolist())
            against_vals.extend(away_rows["HC"].dropna().astype(float).tolist())

            if len(for_vals) == 0 or len(against_vals) == 0:
                continue

            profiles[t] = {
                "for_avg": float(np.mean(for_vals)),
                "against_avg": float(np.mean(against_vals)),
            }

        return profiles

    def _get_corner_profiles_cached(self, historical_df: pd.DataFrame):
        df_id = id(historical_df)
        if self._profiles_cache_df_id == df_id and self._profiles_cache is not None:
            return self._profiles_cache

        profiles = self._build_corner_profiles(historical_df)
        self._profiles_cache_df_id = df_id
        self._profiles_cache = profiles
        return profiles

    # ==================================================
    # FORM (последние N игр) — residual vs нормы соперника
    # ==================================================
    def _compute_form_factor_from_file(
        self,
        form_df: pd.DataFrame,
        team: str,
        opponent_profiles: dict,
        n_games: int,
        beta: float,
        clip_low: float,
        clip_high: float,
        debug_print: bool = False,
    ):
        """
        form_df формат:
          Date,p1,p2,score_p1,score_p2
        где score_* = угловые

        residual:
          attack_resid  = corners_for - opp_against_avg
          defense_resid = opp_for_avg - corners_against
          residual      = attack_resid + defense_resid

        form_factor = exp(beta * mean(residuals)) и потом clip.
        """
        if form_df is None or len(form_df) == 0:
            return 1.0

        games = form_df[(form_df["p1"] == team) | (form_df["p2"] == team)].copy()
        if len(games) == 0:
            return 1.0

        games = games.sort_values("Date").tail(int(n_games))

        residuals = []
        debug_rows = []

        for _, r in games.iterrows():
            if r["p1"] == team:
                corners_for = float(r["score_p1"])
                corners_against = float(r["score_p2"])
                opp = str(r["p2"]).strip()
                side = "home"
            else:
                corners_for = float(r["score_p2"])
                corners_against = float(r["score_p1"])
                opp = str(r["p1"]).strip()
                side = "away"

            opp_prof = opponent_profiles.get(opp)
            if not opp_prof:
                continue

            opp_allow = float(opp_prof["against_avg"])
            opp_for = float(opp_prof["for_avg"])

            atk = corners_for - opp_allow
            dfn = opp_for - corners_against
            resid = atk + dfn

            residuals.append(resid)
            if debug_print:
                debug_rows.append((opp, side, corners_for, opp_allow, atk, corners_against, opp_for, dfn, resid))

        if len(residuals) == 0:
            return 1.0

        form_score = float(np.mean(residuals))
        raw = float(np.exp(float(beta) * form_score))
        form_factor = max(min(raw, float(clip_high)), float(clip_low))

        if debug_print:
            print(f"\n🧩 Form debug for {team} (last {len(residuals)} games):")
            for (opp, side, cf, oa, atk, ca, of, dfn, resid) in debug_rows:
                print(
                    f"  vs {opp:<18} ({side}) "
                    f"for={cf:.0f}(opp_allow={oa:.2f}) atk {atk:+.2f} | "
                    f"against={ca:.0f}(opp_for={of:.2f}) def {dfn:+.2f} | sum {resid:+.2f}"
                )
            print(f"  form_score(avg)={form_score:+.2f}")
            print(f"  exp(beta*score)={raw:.3f} -> clipped={form_factor:.3f} (clip {clip_low}-{clip_high}, beta={beta})")

        return float(form_factor)

    # ==================================================
    # TOTAL ANCHOR (мягкая привязка к линии)
    # ==================================================
    @staticmethod
    def _poisson_over_prob(mean: float, line: float) -> float:
        """
        Для суммы Poisson: Total ~ Poisson(mean).
        P(Total > line) = 1 - CDF(floor(line))
        """
        k = int(np.floor(line))
        if mean <= 0:
            return 0.0

        # считаем CDF итеративно без scipy
        # P(0)=exp(-m); P(i)=P(i-1)*m/i
        p0 = np.exp(-mean)
        cdf = p0
        p = p0
        for i in range(1, k + 1):
            p = p * mean / i
            cdf += p

        over = 1.0 - cdf
        return float(max(0.0, min(1.0, over)))

    def _find_scale_for_target_over(self, mean: float, line: float, target_over: float) -> float:
        """
        Подбираем scale, чтобы P(Poisson(mean*scale) > line) ~= target_over
        """
        target_over = float(max(0.001, min(0.999, target_over)))

        lo, hi = 0.3, 3.0
        for _ in range(35):
            mid = (lo + hi) / 2.0
            p_over = self._poisson_over_prob(mean * mid, line)
            if p_over < target_over:
                lo = mid
            else:
                hi = mid
        return float((lo + hi) / 2.0)

    # ==================================================
    # LAMBDAS (strength + form + мягкий anchor)
    # ==================================================
    def _calculate_lambdas(
        self,
        df: pd.DataFrame,
        home_team: str,
        away_team: str,
        team_strength: dict,
        strength_power=None,
        min_lambda=None,
        max_lambda=None,
        form_df: pd.DataFrame = None,
    ):
        strength_power = CONFIG["STRENGTH_POWER"] if strength_power is None else float(strength_power)
        min_lambda = CONFIG["MIN_LAMBDA"] if min_lambda is None else float(min_lambda)
        max_lambda = CONFIG["MAX_LAMBDA"] if max_lambda is None else float(max_lambda)

        # базовые
        home_games = df[df["HomeTeam"] == home_team]["HC"]
        away_games = df[df["AwayTeam"] == away_team]["AC"]

        league_avg_home = float(df["HC"].mean())
        league_avg_away = float(df["AC"].mean())

        base_lambda_home = float(home_games.mean()) if len(home_games) else league_avg_home
        base_lambda_away = float(away_games.mean()) if len(away_games) else league_avg_away

        # strength
        s_home = float(team_strength.get(home_team, 1.0))
        s_away = float(team_strength.get(away_team, 1.0))
        ratio = (s_home / max(1e-9, s_away)) ** strength_power

        lambda_home = base_lambda_home * ratio
        lambda_away = base_lambda_away / ratio

        # form
        opponent_profiles = self._get_corner_profiles_cached(df)

        form_home = 1.0
        form_away = 1.0
        if form_df is not None:
            form_home = self._compute_form_factor_from_file(
                form_df=form_df,
                team=home_team,
                opponent_profiles=opponent_profiles,
                n_games=CONFIG["FORM_N_GAMES"],
                beta=CONFIG["FORM_BETA"],
                clip_low=CONFIG["FORM_CLIP_LOW"],
                clip_high=CONFIG["FORM_CLIP_HIGH"],
                debug_print=CONFIG["FORM_DEBUG"],
            )
            form_away = self._compute_form_factor_from_file(
                form_df=form_df,
                team=away_team,
                opponent_profiles=opponent_profiles,
                n_games=CONFIG["FORM_N_GAMES"],
                beta=CONFIG["FORM_BETA"],
                clip_low=CONFIG["FORM_CLIP_LOW"],
                clip_high=CONFIG["FORM_CLIP_HIGH"],
                debug_print=CONFIG["FORM_DEBUG"],
            )

        lambda_home *= form_home
        lambda_away *= form_away

        # мягкая привязка к тоталу (не прибивает, если weight < 1)
        anchor_line = CONFIG["ANCHOR_TOTAL_LINE"]
        anchor_scale = 1.0
        if anchor_line is not None:
            mean_total = float(lambda_home + lambda_away)
            target_over = float(CONFIG["ANCHOR_TARGET_OVER_PROB"])
            best_scale = self._find_scale_for_target_over(mean_total, float(anchor_line), target_over)

            w = float(CONFIG["ANCHOR_WEIGHT"])
            anchor_scale = (1.0 - w) * 1.0 + w * best_scale

            lambda_home *= anchor_scale
            lambda_away *= anchor_scale

        # защита
        lambda_home = max(min(float(lambda_home), max_lambda), min_lambda)
        lambda_away = max(min(float(lambda_away), max_lambda), min_lambda)

        return (
            float(lambda_home),
            float(lambda_away),
            float(base_lambda_home),
            float(base_lambda_away),
            float(s_home),
            float(s_away),
            float(ratio),
            float(form_home),
            float(form_away),
            float(anchor_scale),
            anchor_line,
        )

    # ==================================================
    # FAVORITE + SIM
    # ==================================================
    def _determine_favorite(self, lambda_home, lambda_away):
        diff = float(lambda_home) - float(lambda_away)
        if abs(diff) < 0.5:
            return "draw"
        return "home" if diff > 0 else "away"

    def _monte_carlo_simulation(self, lambda_home, lambda_away):
        np.random.seed(42)
        home = np.random.poisson(float(lambda_home), self.n_simulations)
        away = np.random.poisson(float(lambda_away), self.n_simulations)
        return home, away, home - away, home + away

    # ==================================================
    # 1X2 corners
    # ==================================================
    def _calculate_1x2(self, diff):
        n = len(diff)
        p_home = float(np.sum(diff > 0) / n)
        p_draw = float(np.sum(diff == 0) / n)
        p_away = float(np.sum(diff < 0) / n)
        o1, ox, o2 = normalize_odds_triplet(p_home, p_draw, p_away, self.margin)
        return {
            "P1": o1,
            "X": ox,
            "P2": o2,
            "p_home": p_home,
            "p_draw": p_draw,
            "p_away": p_away,
        }

    # ==================================================
    # HANDICAPS (фиксированные стороны: HomeTeam / AwayTeam)
    # ==================================================
    def _calculate_handicaps_fixed_sides(self, diff):
        n = len(diff)
        handicaps = {}

        def _ah0_effective_probs(diff_arr):
            # AH(0): ничья = возврат -> считаем "эффективные" вероятности без push
            p_win = np.sum(diff_arr > 0) / n
            p_lose = np.sum(diff_arr < 0) / n
            p_push = 1.0 - (p_win + p_lose)

            denom = max(1e-12, 1.0 - p_push)
            return (p_win / denom), (p_lose / denom)

        # AH(0)
        p_home0, p_away0 = _ah0_effective_probs(diff)
        odd_home0, odd_away0 = normalize_odds_pair(p_home0, p_away0, self.margin)

        # Home -1.5 vs Away +1.5
        p_home_m15 = np.sum(diff >= 2) / n
        p_away_p15 = np.sum(diff >= -1) / n
        odd_home_m15, odd_away_p15 = normalize_odds_pair(p_home_m15, p_away_p15, self.margin)

        # Home -2.5 vs Away +2.5
        p_home_m25 = np.sum(diff >= 3) / n
        p_away_p25 = np.sum(diff >= -2) / n
        odd_home_m25, odd_away_p25 = normalize_odds_pair(p_home_m25, p_away_p25, self.margin)

        # Away -1.5 vs Home +1.5
        p_away_m15 = np.sum(diff <= -2) / n
        p_home_p15 = np.sum(diff <= 1) / n
        odd_away_m15, odd_home_p15 = normalize_odds_pair(p_away_m15, p_home_p15, self.margin)

        # Away -2.5 vs Home +2.5
        p_away_m25 = np.sum(diff <= -3) / n
        p_home_p25 = np.sum(diff <= 2) / n
        odd_away_m25, odd_home_p25 = normalize_odds_pair(p_away_m25, p_home_p25, self.margin)

        handicaps["HomeTeam"] = {
            "name": "1-я команда (Дома)",
            "F(0)": odd_home0,
            "F(-1.5)": odd_home_m15,
            "F(-2.5)": odd_home_m25,
            "F(+1.5)": odd_home_p15,
            "F(+2.5)": odd_home_p25,
        }
        handicaps["AwayTeam"] = {
            "name": "2-я команда (Гости)",
            "F(0)": odd_away0,
            "F(-1.5)": odd_away_m15,
            "F(-2.5)": odd_away_m25,
            "F(+1.5)": odd_away_p15,
            "F(+2.5)": odd_away_p25,
        }

        return handicaps

    # ==================================================
    # TOTALS + IT
    # ==================================================
    def _calculate_totals(self, total):
        n = len(total)
        out = {}
        for line in CONFIG["TOTAL_LINES"]:
            p_over = np.sum(total > line) / n
            p_under = np.sum(total < line) / n
            out[f"Over_{line}"], out[f"Under_{line}"] = normalize_odds_pair(p_over, p_under, self.margin)
        return out

    def _calculate_individual_totals(self, corners):
        n = len(corners)
        out = {}
        for line in CONFIG["IT_LINES"]:
            p_over = np.sum(corners > line) / n
            p_under = np.sum(corners < line) / n
            out[f"IT_{line}_over"], out[f"IT_{line}_under"] = normalize_odds_pair(p_over, p_under, self.margin)
        return out
