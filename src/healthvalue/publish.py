"""Render research figures, a written report and a portable dashboard dataset."""

import json
import shutil

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from .config import PROCESSED, RAW, REPORTS, WEB

NAVY, TEAL, ORANGE, PAPER = "#162c39", "#217f80", "#d67742", "#f7f6f2"


def setup_plot():
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.labelcolor": NAVY,
            "text.color": NAVY,
            "xtick.color": NAVY,
            "ytick.color": NAVY,
            "figure.facecolor": PAPER,
            "axes.facecolor": PAPER,
            "savefig.facecolor": PAPER,
        }
    )


def figures(panel, associations, forecast):
    setup_plot()
    folder = REPORTS / "figures"
    folder.mkdir(exist_ok=True)
    latest = panel.loc[panel.year.eq(2023)].dropna(subset=["spend_ppp", "treatable"])
    fig, ax = plt.subplots(figsize=(11, 6.3), layout="constrained")
    ax.scatter(
        latest.spend_ppp,
        latest.treatable,
        s=70,
        color=TEAL,
        alpha=0.75,
        edgecolor="white",
    )
    for code in ["USA", "POL", "KOR", "JPN", "CHE", "MEX", "LVA", "BRA", "DEU", "ZAF"]:
        row = latest.loc[latest.iso3.eq(code)]
        if not row.empty:
            ax.annotate(
                code,
                (row.iloc[0].spend_ppp, row.iloc[0].treatable),
                xytext=(7, 5),
                textcoords="offset points",
                fontsize=9,
            )
    ax.set_xscale("log")
    ax.set(
        xlabel="Health spending per person, current international $ (PPP, log scale)",
        ylabel="Treatable deaths per 100,000, age-standardised",
        title=f"HEALTHVALUE ATLAS  /  Spending and outcomes, 2023\n{len(latest)} countries with both indicators",
    )
    ax.grid(alpha=0.16)
    fig.savefig(folder / "spending_outcomes.png", dpi=170)
    plt.close(fig)

    estimates = pd.DataFrame(associations["estimates"])
    fig, ax = plt.subplots(figsize=(11, 5.4), layout="constrained")
    y = np.arange(len(estimates))
    ax.errorbar(
        estimates.change_10pct,
        y,
        xerr=np.vstack(
            [
                estimates.change_10pct - estimates.change_10pct_low,
                estimates.change_10pct_high - estimates.change_10pct,
            ]
        ),
        fmt="o",
        color=TEAL,
        capsize=5,
        markersize=8,
    )
    ax.axvline(0, color=ORANGE, linestyle=":")
    ax.set_yticks(y, estimates.specification)
    ax.invert_yaxis()
    ax.set(
        xlabel="Associated change in treatable mortality for +10% spending (%)",
        title="Association depends on the research design\n95% country-clustered confidence intervals",
    )
    ax.grid(axis="x", alpha=0.16)
    fig.savefig(folder / "association_sensitivity.png", dpi=170)
    plt.close(fig)

    metrics = pd.DataFrame(forecast["metrics"])
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.2), layout="constrained")
    for ax, col, title in zip(
        axes,
        ["validation_mae", "test_mae"],
        ["Model selection: 2016-2019", "Held-out evaluation: 2022-2023"],
    ):
        ax.barh(
            metrics.model,
            metrics[col],
            color=[ORANGE if x else TEAL for x in metrics.selected],
        )
        ax.invert_yaxis()
        ax.set(title=title, xlabel="MAE, deaths per 100,000")
        ax.grid(axis="x", alpha=0.16)
    fig.suptitle("Can ML improve on last year's mortality rate?", fontsize=15)
    fig.savefig(folder / "forecast_benchmark.png", dpi=170)
    plt.close(fig)

    importance = pd.DataFrame(forecast["validation_importance"])
    if not importance.empty:
        display_names = {
            "lag_treatable": "Prior treatable mortality",
            "lag_preventable": "Prior preventable mortality",
            "log_lag_spend_real_proxy": "Prior real spending proxy",
            "log_lag_gdp_ppp_constant": "Prior real GDP",
            "lag_age65_pct": "Prior age 65+ share",
            "lag_oop_share": "Prior household payment share",
            "lag_public_share": "Prior public spending share",
            "lag_urban_pct": "Prior urban share",
            "year": "Forecast year",
            "iso3": "Country",
        }
        fig, ax = plt.subplots(figsize=(11, 5.5), layout="constrained")
        ax.barh(
            [display_names[x] for x in importance.feature],
            importance.mae_increase,
            color=TEAL,
        )
        ax.invert_yaxis()
        ax.axvline(0, color=NAVY, linewidth=0.6)
        ax.set(
            xlabel="Increase in MAE after shuffling a feature",
            title="What the selected model uses\nPermutation importance on 2019 validation, 20 repeats",
        )
        ax.grid(axis="x", alpha=0.16)
        fig.savefig(folder / "validation_importance.png", dpi=170)
        plt.close(fig)

    columns = ["treatable", "spend_ppp", "gdp_ppp_constant", "age65_pct", "oop_share"]
    missing = panel.groupby("year")[columns].agg(lambda s: s.isna().mean() * 100).T
    fig, ax = plt.subplots(figsize=(11, 4.4), layout="constrained")
    im = ax.imshow(
        missing,
        cmap="YlOrBr",
        vmin=0,
        vmax=max(20, missing.to_numpy().max()),
        aspect="auto",
    )
    ax.set_xticks(range(len(missing.columns)), missing.columns)
    ax.set_yticks(
        range(len(columns)),
        [
            "Treatable mortality",
            "Health spending",
            "Real GDP per person",
            "Age 65+",
            "Out-of-pocket share",
        ],
    )
    ax.set_title("Missingness across the full 46-country grid")
    fig.colorbar(im, ax=ax, label="Missing observations (%)")
    fig.savefig(folder / "data_coverage.png", dpi=170)
    plt.close(fig)


def main():
    panel = pd.read_csv(PROCESSED / "panel.csv")
    associations = json.loads((REPORTS / "associations.json").read_text())
    forecast = json.loads((REPORTS / "forecast.json").read_text())
    quality = json.loads((REPORTS / "data_quality.json").read_text())
    manifest = json.loads((RAW / "manifest.json").read_text())
    latest = panel.loc[panel.year.eq(2023)].dropna(subset=["spend_ppp", "treatable"])
    rho = float(spearmanr(latest.spend_ppp, latest.treatable).statistic)
    paired = (
        panel.loc[panel.year.eq(2010), ["iso3", "treatable"]]
        .merge(
            panel.loc[panel.year.eq(2023), ["iso3", "treatable"]],
            on="iso3",
            suffixes=("_2010", "_2023"),
        )
        .dropna()
    )
    median_change = float(
        ((paired.treatable_2023 / paired.treatable_2010 - 1) * 100).median()
    )
    findings = {
        "cross_section_n": len(latest),
        "spearman_spend_mortality": rho,
        "paired_countries": len(paired),
        "median_country_change_pct": median_change,
        "median_spend_ppp": float(latest.spend_ppp.median()),
        "median_treatable": float(latest.treatable.median()),
    }
    (REPORTS / "findings.json").write_text(
        json.dumps(findings, indent=2), encoding="utf-8"
    )
    figures(panel, associations, forecast)
    columns = [
        "iso3",
        "country",
        "region",
        "income_group",
        "year",
        "treatable",
        "preventable",
        "avoidable",
        "spend_ppp",
        "spend_real_proxy",
        "gdp_ppp_constant",
        "age65_pct",
        "oop_share",
        "public_share",
        "life_expectancy",
        "health_gdp_pct",
        "population",
    ]
    payload = {
        "panel": json.loads(
            panel[columns].to_json(orient="records", double_precision=6)
        ),
        "associations": associations,
        "forecast": forecast,
        "quality": quality,
        "findings": findings,
        "sources": manifest,
        "predictions": json.loads(
            pd.read_csv(REPORTS / "test_predictions.csv").to_json(
                orient="records", double_precision=6
            )
        ),
    }
    (WEB / "data").mkdir(parents=True, exist_ok=True)
    (WEB / "data" / "atlas.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False),
        encoding="utf-8",
    )
    shutil.copy(PROCESSED / "panel.csv", WEB / "data" / "panel.csv")
    main = associations["main"]
    best = next(x for x in forecast["metrics"] if x["selected"])
    baseline = next(x for x in forecast["metrics"] if x["model"] == "Persistence")
    improvement = 100 * (1 - best["test_mae"] / baseline["test_mae"])
    report = f"""# HealthValue Atlas: результаты исследования

## Исследовательский вопрос

Как расходы на здравоохранение связаны со смертностью, которую можно снизить своевременным лечением? Можно ли точнее предсказать показатель на следующий год, если добавить экономические и демографические признаки?

## Данные

Срез охватывает {quality["countries"]} стран за 2010-2023 годы. Полная сетка содержит {quality["grid_rows"]} строк. Для {quality["mortality_rows"]} строк есть показатель смертности. В сравнении расходов и смертности за 2023 год участвуют {len(latest)} стран. Состав выборки задаёт доступность данных ОЭСР. Это не репрезентативная выборка всех стран мира.

Расходы и структура финансирования приходят из ВОЗ GHED через World Bank WDI. ОЭСР даёт возрастные стандартизованные показатели смертности до 75 лет. WDI даёт доход и демографию. Все исходные ответы API и их SHA-256 входят в репозиторий. Дата загрузки есть в data/raw/manifest.json. Дата загрузки не равна году наблюдения.

## Что показал анализ

1. В срезе за 2023 год ранговая корреляция расходов и смертности равна {rho:.2f}. Это связь между странами. Она сама по себе не показывает эффект дополнительного бюджета.
2. В {len(paired)} странах есть данные и за 2010, и за 2023 год. Медиана относительного изменения смертности по этим странам равна {median_change:.1f}%. Каждая страна имеет одинаковый вес.
3. После учёта эффектов стран и лет, дохода, доли населения 65+ и прямых платежей домохозяйств рост расходов на 10% связан с изменением смертности на {main["change_10pct"]:.2f}%. 95% доверительный интервал: от {main["change_10pct_low"]:.2f}% до {main["change_10pct_high"]:.2f}%. Расходы и контрольные признаки входят с лагом в один год.
4. По временной валидации выбран вариант {forecast["selected_model"]}. Его MAE на тесте за 2022-2023 годы равна {best["test_mae"]:.2f} смерти на 100 000. MAE прогноза по прошлому году равна {baseline["test_mae"]:.2f}. Относительное улучшение: {improvement:.1f}%. Отрицательное число означает ухудшение.
5. Калибровочный интервал с номинальным уровнем 90% покрывает {100 * best["interval_coverage"]:.1f}% тестовых наблюдений. Это эмпирическая проверка, а не гарантия покрытия для будущих лет.

## Как читать результаты

Сравнение стран и анализ изменений внутри страны отвечают на разные вопросы. Богатые страны могут одновременно больше тратить, иметь другую структуру населения и лучше контролировать факторы риска. Эффекты стран убирают постоянные различия. Эффекты лет учитывают общие годовые сдвиги. Они не устраняют все причины смещения.

Основная модель оценивает связь. Она не доказывает, что увеличение бюджета приведёт к указанному снижению смертности. Возможны обратная причинность, изменения качества данных и факторы, которых нет в модели. Доверительный интервал описывает неопределённость коэффициента при принятых предположениях.

Мы проверяем пять спецификаций: объединённую модель, эффекты стран и лет, период до пандемии, страны с высоким доходом и отдельные линейные тренды стран. Результаты доступны в association_estimates.csv. Группа дохода отражает текущую классификацию Всемирного банка.

## Прогноз и контроль утечки

Модель предсказывает годовое изменение показателя. Прогноз по прошлому году служит базой. Временная валидация включает четыре шага: 2016, 2017, 2018 и 2019 год. Каждый шаг использует только более ранние годы. Заполнение пропусков и масштабирование обучаются заново внутри каждого шага.

Финальное обучение заканчивается в 2019 году. 2020-2021 годы нужны только для калибровки интервалов. 2022-2023 годы составляют тест. Выбор модели зависит только от валидации. Предикторы используют сведения за предыдущий год. Значение за 2022 год допустимо как признак прогноза на 2023 год, но не как новая строка обучения.

Это ретроспективная проверка прогноза на год вперёд. Она предполагает, что все показатели прошлого года уже известны. В реальности публикация данных запаздывает, а ряды пересматривают. Исторические версии данных здесь не восстановлены. Поэтому результат нельзя трактовать как качество прогноза в реальном времени.

Изменение MAE относительно базы проверено бутстрэпом по странам. 95% интервал абсолютного выигрыша: {forecast["improvement_vs_persistence_ci95"][0]:.2f} - {forecast["improvement_vs_persistence_ci95"][1]:.2f} смерти на 100 000. Положительное значение означает преимущество выбранной модели. Годы одной страны остаются в одном блоке. Общие межстрановые шоки этот бутстрэп полностью не учитывает.

## Сопоставимость и пропуски

Для сравнения стран в одном году используются расходы на человека в текущих международных долларах по ППС. Для временной модели строится прокси в постоянных ценах: доля расходов в ВВП × реальный ВВП на человека по ППС / 100. Этот пересчёт использует общий дефлятор экономики. Он не измеряет отдельную динамику цен медицинских услуг.

Пропуски целевой переменной не заполняются. Лаг требует ровно предыдущий календарный год. Эконометрическая модель использует полные наблюдения. В прогнозе медианы признаков рассчитаны только на обучающем периоде. Средние и медианы по странам не взвешены по населению. Изменение состава стран может влиять на годовые сводки.

Возрастная стандартизация уже снижает влияние возрастной структуры на смертность. Доля людей 65+ входит в модель как характеристика спроса и нагрузки на систему. Она не служит повторной стандартизацией исхода.

## Практическое применение

Атлас помогает выбрать сопоставимые страны, проверить устойчивость связи и сформулировать вопросы для отдельного исследования. Он не ранжирует качество отдельных больниц и не назначает оптимальный бюджет. Для оценки реформ нужен отдельный дизайн с датой вмешательства и обоснованной контрольной группой.

## Артефакты

- figures/spending_outcomes.png: расходы и смертность.
- figures/association_sensitivity.png: устойчивость эконометрической оценки.
- figures/forecast_benchmark.png: сравнение моделей.
- figures/data_coverage.png: пропуски по годам.
- model_metrics.csv: все метрики.
- test_predictions.csv: прогнозы и интервалы на тесте.
- main_coefficients.csv: коэффициенты основной модели.
- validation_importance.csv: важность признаков на валидации 2019 года. Признак перемешивается 20 раз. Рост MAE показывает потерю точности. Это не причинный эффект. Взаимосвязь признаков может снижать отдельные оценки важности.
- errors_by_year.csv и errors_by_country.csv: разбор ошибок по годам и странам.

Источники и определения: [описание данных](../docs/DATA.md). Дизайн анализа: [методология](../docs/METHODOLOGY.md).
"""
    (REPORTS / "ANALYSIS_RU.md").write_text(report, encoding="utf-8")
    print(json.dumps(findings, indent=2))


if __name__ == "__main__":
    main()
