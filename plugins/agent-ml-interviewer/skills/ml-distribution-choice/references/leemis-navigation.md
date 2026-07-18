# Навігація чартом UDR: як знаходити й цитувати докази

Чарт: Leemis & McQueston (2008), *Univariate Distribution Relationships*, The
American Statistician 62(1); інтерактивна версія —
`https://www.math.wm.edu/~leemis/chart/UDR/UDR.html`. 76 розподілів
(19 дискретних — прямокутники, 57 неперервних — заокруглені), кожен клік — PDF.

**Стан перевірено 2026-07-18:** сторінка 125 752 байти, 280 унікальних PDF.
Повний машинний індекс — [`udr-index.md`](udr-index.md) (греп замість мережі).

## Як фетчити

Ланцюг сертифікатів сайту неповний, тому стандартний fetch (Node, WebFetch)
падає з «unable to verify the first certificate». Робочі варіанти:

```bash
curl -sS --ssl-no-revoke -o UDR.html "https://www.math.wm.edu/~leemis/chart/UDR/UDR.html"
curl -sS --ssl-no-revoke -o BinomialPoisson.pdf \
     "https://www.math.wm.edu/~leemis/chart/UDR/PDFs/BinomialPoisson.pdf"
# fallback: curl -sSk (вимикає перевірку взагалі — лише для цього сайту)
```

PDF далі читається інструментом читання файлів (вони короткі, 1–2 сторінки).

## URL-схема

Все живе в `https://www.math.wm.edu/~leemis/chart/UDR/PDFs/<Файл>.pdf`:

| Вид | Шаблон імені | Приклад |
|---|---|---|
| Картка розподілу | `<Name>` | `Poisson.pdf`, `Weibull.pdf` |
| Доказ стрілки | `<From><To>` | `BinomialPoisson.pdf` |
| Паралельні дуги пари | `<From><To>B` / `<From><To>T` | `GammaChisquareB.pdf` / `...T.pdf` |
| Доказ властивості | `<Name><Літера>` | `NormalL.pdf`, `PoissonC.pdf` |
| Пояснення типу зв'язку | назва типу | `Limiting.pdf`, `Bayesian.pdf`, `Specialcases.pdf`, `Transformations.pdf` |

Імена розподілів — одна велика літера на початку (`Gammapoisson`,
`Standarduniform`, `Noncentralchisquare`), **крім** `IDB` і `TSP` (усі великі).
Повний список 76 імен — в індексі.

### Колізії, які збивають з пантелику

- `TF.pdf`, `ChisquareF.pdf`, `ExponentialF.pdf`, `GeometricF.pdf`,
  `NoncentralfF.pdf`, `NoncentraltT.pdf` — це **стрілки до розподілів F і t**,
  а не властивості F/T (бо F і t — теж розподіли, однолітерні).
- Властивість memoryless експоненційного — **`ExponentialForgetfulness.pdf`**,
  не `ExponentialF.pdf`.
- Суфікси `B`/`T` позначають **дві різні дуги між тією самою парою**. Звірено на
  Gamma↔Chi-square: `T` = окремий випадок (α=2, n=2β), `B` = трансформація
  (2X/α ~ χ²(2β)). Для інших пар семантика B/T не гарантована — відкривайте обидва.
  Плоского файлу без суфікса для таких пар не існує (перевірено: 0 згадок).
- Пар із B/T — шість: Erlang↔Chisquare, Exponential↔Chisquare, Gamma↔Chisquare,
  Normal↔Standardnormal, Standarduniform↔Exponential, Standarduniform↔Standardpower.

## Що всередині картки розподілу

Перевірено на `Poisson.pdf`: pmf/pdf, **застосування прямим текстом** («potholes
over a stretch of highway, typographical errors in a book, customer arrivals in
an hour, earthquakes in a decade»), CDF, survivor, hazard, cumulative hazard,
медіана, MGF, характеристична функція, **mean/variance/skewness/kurtosis** і
APPL-верифікація. Тобто картка — готове джерело для тверджень виду
«V[X] = µ ⟹ гетероскедастичність вбудована ⟹ Poisson deviance, а не MSE».

## Чотири типи стрілок = чотири типи аргументів

| Тип (легенда чарта) | Лінія | Питання, на яке відповідає |
|---|---|---|
| Special case | суцільна | чи достатньо простішої моделі (зафіксувати параметр) |
| Transformation | суцільна | яка шкала природна (log, квадрат, обернена) |
| Limiting | пунктирна | коли наближення допустиме (n→∞, p→0) |
| Bayesian | крапчаста | звідки overdispersion (параметр сам випадковий) |

## Докази, звірені дослівно (2026-07-18)

**`BinomialPoisson.pdf`** (limiting): «The Poisson(µ) distribution is the limit
of the binomial(n, p) distribution with µ = np as n → ∞» — повний вивід через
розклад біноміальних коефіцієнтів; чесна примітка, що Maple/APPL границю
автоматично не взяв, підтверджено ручним `limit(...)`.

**`PoissonGammapoisson.pdf`** (Bayesian): «If X ~ Poisson(µ) and µ ~ gamma(α, β)
then the pmf of X is Γ(x+β)αˣ/[Γ(β)(1+α)^{β+x}x!], known as the gamma–Poisson
distribution» — compound-інтеграл виписано повністю.

**`GammapoissonPascal.pdf`** (special case): «The Pascal distribution is a
special case of the gamma–Poisson distribution when α = (1−p)/p and β = n» —
зведення до pmf `C(n+x−1, x) pⁿ(1−p)ˣ`.

Разом ці два — формальний ланцюжок **«Poisson з варіативною інтенсивністю ⟹
NegBin»**, тобто доказ поради «overdispersed лічильники → NegBin, але спершу
шукайте коваріату, що пояснює варіацію µ».

**`GammaChisquareT.pdf`**: χ² — окремий випадок gamma при n=2β, α=2.
**`GammaChisquareB.pdf`**: якщо X ~ gamma(α,β), то 2X/α ~ χ²(2β) — техніка
трансформації з якобіаном.

## Помилки самого чарта (сайт веде їх список — цитувати чесно)

Розділ «Are there errors on the chart?» на сторінці:

- **Не належить чарту:** Gamma-normal — двовимірний розподіл.
- **Хибні властивості:** Standard Cauchy (S), Standard Wald (S), von Mises (S).
- **Недоведені властивості:** Cauchy (C), Cauchy (I), Inverse Gaussian (L),
  Lognormal (P). Прим.: файл `LognormalP.pdf` існує і містить аргумент через
  L-властивість нормального; сайт, однак, рахує доведення незавершеним —
  цитуйте як «класичний результат; доказ на сайті позначений незавершеним».
- **Хибний зв'язок:** Beta-binomial → Negative hypergeometric (правильно
  a=n₁, b=n₃−n₁, n=n₂, corr. Jean Peyhardi).
- **Недоведені зв'язки:** Doubly noncentral F → Noncentral F; Generalized gamma
  → Lognormal; Hypoexponential → Erlang; Inverse Gaussian → Chi-square;
  Inverse Gaussian → Standard normal; Normal → Noncentral chi-square;
  Pascal → Normal (на чарті має бути µ = n(1−p)/p); Pascal → Poisson.
- **Хибні параметри:** Standard uniform → Logistic-exponential.
- `CauchyC.pdf` позначений «[UNDER CONSTRUCTION!]»; результат класично істинний
  (стабільний закон з індексом 1), але сайт його не доводить.

Правило цитування: **незавершений доказ на сайті — привід відкрити підручник,
а не спростування результату.**

## Як цитувати у відповіді

Формат: твердження → файл → один рядок теореми. Приклад:

> Overdispersion (VMR = 2.4) означає варіативну інтенсивність: якщо µ ~ gamma,
> маргінал лічильника — gamma-Poisson (`PoissonGammapoisson.pdf`: «If X ~
> Poisson(µ) and µ ~ gamma(α,β)…»), а це NegBin (`GammapoissonPascal.pdf`).
> Тому модель — NegativeBinomial із log-link; але спершу перевіряю, чи не
> пояснює варіацію сегмент/година.

Не цитуйте по пам'яті те, що можна взяти з файлу: індекс локальний, фетч —
одна команда.
