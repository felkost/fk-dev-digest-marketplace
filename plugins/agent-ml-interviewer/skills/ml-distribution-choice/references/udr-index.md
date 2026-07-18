# Індекс посилань чарта UDR (Leemis & McQueston, William & Mary)

Згенеровано механічно з UDR.html, знято **2026-07-18** командою
`curl --ssl-no-revoke https://www.math.wm.edu/~leemis/chart/UDR/UDR.html`
(ланцюг сертифікатів сайту неповний, тому звичайний fetch падає; у Git Bash
працює і `curl -k`). Сторінка 125 752 байти.

Інвентар: **280 унікальних PDF** = 76 карток розподілів
(рівно 76, як в анотації сайту; 'IDB' і 'TSP' пишуться великими) +
124 доказів стрілок + 76 доказів властивостей +
4 пояснень типів зв'язків (Specialcases, Transformations, Limiting, Bayesian).

URL будь-якого запису: `https://www.math.wm.edu/~leemis/chart/UDR/PDFs/<файл>.pdf`.
Суфікси `B`/`T` у стрілках — дві паралельні дуги тієї самої пари вершин
(перевірено: GammaChisquareT = окремий випадок α=2, n=2β;
GammaChisquareB = трансформація 2X/α ~ χ²(2β)).

Колізії літери властивості з назвою розподілу: `TF`, `ChisquareF`,
`ExponentialF`, `GeometricF`, `NoncentralfF`, `NoncentraltT` — це стрілки
до розподілів F і t; властивість memoryless експоненційного лежить у
`ExponentialForgetfulness.pdf`.

Формат рядка: `файл | від | до-або-літера`.

## Картки розподілів (76)

- Arcsin | Arcsin | -
- Arctangent | Arctangent | -
- Benford | Benford | -
- Bernoulli | Bernoulli | -
- Beta | Beta | -
- Betabinomial | Betabinomial | -
- Betapascal | Betapascal | -
- Binomial | Binomial | -
- Cauchy | Cauchy | -
- Chi | Chi | -
- Chisquare | Chisquare | -
- Discreteuniform | Discreteuniform | -
- Discreteweibull | Discreteweibull | -
- Doublynoncentralf | Doublynoncentralf | -
- Doublynoncentralt | Doublynoncentralt | -
- Erlang | Erlang | -
- Error | Error | -
- Exponential | Exponential | -
- Exponentialpower | Exponentialpower | -
- Extremevalue | Extremevalue | -
- F | F | -
- Gamma | Gamma | -
- Gammanormal | Gammanormal | -
- Gammapoisson | Gammapoisson | -
- Generalizedgamma | Generalizedgamma | -
- Generalizedpareto | Generalizedpareto | -
- Geometric | Geometric | -
- Gompertz | Gompertz | -
- Hyperbolicsecant | Hyperbolicsecant | -
- Hyperexponential | Hyperexponential | -
- Hypergeometric | Hypergeometric | -
- Hypoexponential | Hypoexponential | -
- IDB | IDB | -
- Inversegaussian | Inversegaussian | -
- Invertedbeta | Invertedbeta | -
- Invertedgamma | Invertedgamma | -
- Kolmogorovsmirnov | Kolmogorovsmirnov | -
- Laplace | Laplace | -
- Logarithm | Logarithm | -
- Loggamma | Loggamma | -
- Logistic | Logistic | -
- Logisticexponential | Logisticexponential | -
- Loglogistic | Loglogistic | -
- Lognormal | Lognormal | -
- Lomax | Lomax | -
- Makeham | Makeham | -
- Minimax | Minimax | -
- Muth | Muth | -
- Negativehypergeometric | Negativehypergeometric | -
- Noncentralbeta | Noncentralbeta | -
- Noncentralchisquare | Noncentralchisquare | -
- Noncentralf | Noncentralf | -
- Noncentralt | Noncentralt | -
- Normal | Normal | -
- Pareto | Pareto | -
- Pascal | Pascal | -
- Poisson | Poisson | -
- Polya | Polya | -
- Power | Power | -
- Powerseries | Powerseries | -
- Rayleigh | Rayleigh | -
- Rectangular | Rectangular | -
- Standardcauchy | Standardcauchy | -
- Standardnormal | Standardnormal | -
- Standardpower | Standardpower | -
- Standardtriangular | Standardtriangular | -
- Standarduniform | Standarduniform | -
- Standardwald | Standardwald | -
- T | T | -
- TSP | TSP | -
- Triangular | Triangular | -
- Uniform | Uniform | -
- Vonmises | Vonmises | -
- Weibull | Weibull | -
- Zeta | Zeta | -
- Zipf | Zipf | -

## Докази стрілок

- BernoulliBinomial | Bernoulli | Binomial
- BetaArcsin | Beta | Arcsin
- BetaInvertedbeta | Beta | Invertedbeta
- BetaNormal | Beta | Normal
- BetaStandarduniform | Beta | Standarduniform
- BetabinomialNegativehypergeometric | Betabinomial | Negativehypergeometric
- BetabinomialRectangular | Betabinomial | Rectangular
- BinomialBernoulli | Binomial | Bernoulli
- BinomialBetabinomial | Binomial | Betabinomial
- BinomialNormal | Binomial | Normal
- BinomialPoisson | Binomial | Poisson
- CauchyArctangent | Cauchy | Arctangent
- CauchyStandardcauchy | Cauchy | Standardcauchy
- ChisquareChi | Chisquare | Chi
- ChisquareErlang | Chisquare | Erlang
- ChisquareExponential | Chisquare | Exponential
- ChisquareF | Chisquare | F
- DiscreteuniformRectangular | Discreteuniform | Rectangular
- DiscreteweibullGeometric | Discreteweibull | Geometric
- DoublynoncentralfNoncentralf | Doublynoncentralf | Noncentralf
- DoublynoncentraltNoncentralt | Doublynoncentralt | Noncentralt
- ErlangChisquareB | Erlang | Chisquare (дуга B)
- ErlangChisquareT | Erlang | Chisquare (дуга T)
- ErlangExponential | Erlang | Exponential
- ErrorLaplace | Error | Laplace
- ExponentialChisquareB | Exponential | Chisquare (дуга B)
- ExponentialChisquareT | Exponential | Chisquare (дуга T)
- ExponentialErlang | Exponential | Erlang
- ExponentialF | Exponential | F
- ExponentialHyperexponential | Exponential | Hyperexponential
- ExponentialHypoexponential | Exponential | Hypoexponential
- ExponentialLaplace | Exponential | Laplace
- ExponentialRayleigh | Exponential | Rayleigh
- ExponentialWeibull | Exponential | Weibull
- FChisquare | F | Chisquare
- GammaBeta | Gamma | Beta
- GammaChisquareB | Gamma | Chisquare (дуга B)
- GammaChisquareT | Gamma | Chisquare (дуга T)
- GammaErlang | Gamma | Erlang
- GammaInvertedbeta | Gamma | Invertedbeta
- GammaInvertedgamma | Gamma | Invertedgamma
- GammaLoggamma | Gamma | Loggamma
- GammapoissonPascal | Gammapoisson | Pascal
- GeneralizedgammaGamma | Generalizedgamma | Gamma
- GeneralizedgammaLognormal | Generalizedgamma | Lognormal
- GeneralizedparetoPareto | Generalizedpareto | Pareto
- GeometricF | Geometric | F
- GeometricPascal | Geometric | Pascal
- HyperexponentialExponential | Hyperexponential | Exponential
- HypergeometricBinomial | Hypergeometric | Binomial
- HypoexponentialErlang | Hypoexponential | Erlang
- IDBExponential | IDB | Exponential
- IDBRayleigh | IDB | Rayleigh
- InversegaussianChisquare | Inversegaussian | Chisquare
- InversegaussianStandardnormal | Inversegaussian | Standardnormal
- InversegaussianStandardwald | Inversegaussian | Standardwald
- KolmogorovsmirnovUniform | Kolmogorovsmirnov | Uniform
- LaplaceError | Laplace | Error
- LaplaceExponential | Laplace | Exponential
- LogisticexponentialExponential | Logisticexponential | Exponential
- LoglogisticLogistic | Loglogistic | Logistic
- LoglogisticLomax | Loglogistic | Lomax
- LomaxLoglogistic | Lomax | Loglogistic
- MakehamGompertz | Makeham | Gompertz
- MinimaxStandardpower | Minimax | Standardpower
- MuthExponential | Muth | Exponential
- NegativehypergeometricBinomial | Negativehypergeometric | Binomial
- NoncentralbetaBeta | Noncentralbeta | Beta
- NoncentralchisquareChisquare | Noncentralchisquare | Chisquare
- NoncentralfF | Noncentralf | F
- NoncentraltT | Noncentralt | T
- NormalChisquare | Normal | Chisquare
- NormalGammanormal | Normal | Gammanormal
- NormalLognormal | Normal | Lognormal
- NormalNoncentralchisquare | Normal | Noncentralchisquare
- NormalStandardnormalB | Normal | Standardnormal (дуга B)
- NormalStandardnormalT | Normal | Standardnormal (дуга T)
- ParetoExponential | Pareto | Exponential
- PascalBetapascal | Pascal | Betapascal
- PascalGeometric | Pascal | Geometric
- PascalNormal | Pascal | Normal
- PascalPoisson | Pascal | Poisson
- PoissonGammapoisson | Poisson | Gammapoisson
- PoissonNormal | Poisson | Normal
- PolyaBinomial | Polya | Binomial
- PowerStandardpower | Power | Standardpower
- PowerseriesLogarithm | Powerseries | Logarithm
- PowerseriesPascal | Powerseries | Pascal
- PowerseriesPoisson | Powerseries | Poisson
- RayleighExponential | Rayleigh | Exponential
- StandardcauchyCauchy | Standardcauchy | Cauchy
- StandardcauchyHyperbolicsecant | Standardcauchy | Hyperbolicsecant
- StandardnormalChi | Standardnormal | Chi
- StandardnormalChisquare | Standardnormal | Chisquare
- StandardnormalNormal | Standardnormal | Normal
- StandardnormalStandardcauchy | Standardnormal | Standardcauchy
- StandardpowerStandarduniform | Standardpower | Standarduniform
- StandarduniformBenford | Standarduniform | Benford
- StandarduniformBeta | Standarduniform | Beta
- StandarduniformExponentialB | Standarduniform | Exponential (дуга B)
- StandarduniformExponentialT | Standarduniform | Exponential (дуга T)
- StandarduniformExponentialpower | Standarduniform | Exponentialpower
- StandarduniformGompertz | Standarduniform | Gompertz
- StandarduniformLogisticexponential | Standarduniform | Logisticexponential
- StandarduniformLoglogistic | Standarduniform | Loglogistic
- StandarduniformPareto | Standarduniform | Pareto
- StandarduniformStandardpowerB | Standarduniform | Standardpower (дуга B)
- StandarduniformStandardpowerT | Standarduniform | Standardpower (дуга T)
- StandarduniformStandardtriangular | Standarduniform | Standardtriangular
- StandarduniformUniform | Standarduniform | Uniform
- TF | T | F
- TSPTriangular | TSP | Triangular
- TSPUniform | TSP | Uniform
- TStandardcauchy | T | Standardcauchy
- TStandardnormal | T | Standardnormal
- TriangularStandardtriangular | Triangular | Standardtriangular
- UniformKolmogorovsmirnov | Uniform | Kolmogorovsmirnov
- UniformStandarduniform | Uniform | Standarduniform
- VonmisesUniform | Vonmises | Uniform
- WeibullExponential | Weibull | Exponential
- WeibullExtremevalue | Weibull | Extremevalue
- WeibullRayleigh | Weibull | Rayleigh
- ZipfDiscreteuniform | Zipf | Discreteuniform
- ZipfZeta | Zipf | Zeta

## Докази властивостей

- ArcsinV | Arcsin | V
- ArctangentS | Arctangent | S
- ArctangentV | Arctangent | V
- BenfordV | Benford | V
- BernoulliM | Bernoulli | M
- BernoulliP | Bernoulli | P
- BernoulliX | Bernoulli | X
- BinomialC | Binomial | C
- CauchyC | Cauchy | C
- CauchyI | Cauchy | I
- CauchyS | Cauchy | S
- CauchyV | Cauchy | V
- ChisquareC | Chisquare | C
- DiscreteuniformR | Discreteuniform | R
- DiscreteuniformV | Discreteuniform | V
- DiscreteweibullV | Discreteweibull | V
- ErlangS | Erlang | S
- ErrorS | Error | S
- ExponentialForgetfulness | Exponential | F
- ExponentialM | Exponential | M
- ExponentialS | Exponential | S
- ExponentialV | Exponential | V
- ExponentialpowerV | Exponentialpower | V
- ExtremevalueM | Extremevalue | M
- ExtremevalueV | Extremevalue | V
- FI | F | I
- GammaC | Gamma | C
- GammaS | Gamma | S
- GeometricM | Geometric | M
- GeometricV | Geometric | V
- GompertzV | Gompertz | V
- HyperbolicsecantV | Hyperbolicsecant | V
- HypoexponentialC | Hypoexponential | C
- InversegaussianL | Inversegaussian | L
- KolmogorovsmirnovV | Kolmogorovsmirnov | V
- LaplaceV | Laplace | V
- LogisticS | Logistic | S
- LogisticV | Logistic | V
- LogisticexponentialS | Logisticexponential | S
- LogisticexponentialV | Logisticexponential | V
- LoglogisticI | Loglogistic | I
- LoglogisticS | Loglogistic | S
- LoglogisticV | Loglogistic | V
- LognormalP | Lognormal | P
- LomaxV | Lomax | V
- MinimaxM | Minimax | M
- MinimaxV | Minimax | V
- NoncentralchisquareC | Noncentralchisquare | C
- NormalL | Normal | L
- ParetoM | Pareto | M
- ParetoV | Pareto | V
- PascalC | Pascal | C
- PoissonC | Poisson | C
- PowerS | Power | S
- PowerV | Power | V
- PowerX | Power | X
- RayleighM | Rayleigh | M
- RayleighS | Rayleigh | S
- RayleighV | Rayleigh | V
- RectangularV | Rectangular | V
- StandardcauchyI | Standardcauchy | I
- StandardcauchyS | Standardcauchy | S
- StandardcauchyV | Standardcauchy | V
- StandardpowerV | Standardpower | V
- StandardpowerX | Standardpower | X
- StandardtriangularV | Standardtriangular | V
- StandarduniformV | Standarduniform | V
- StandardwaldS | Standardwald | S
- TSPV | TSP | V
- TriangularV | Triangular | V
- UniformR | Uniform | R
- UniformV | Uniform | V
- VonmisesS | Vonmises | S
- WeibullM | Weibull | M
- WeibullS | Weibull | S
- WeibullV | Weibull | V

## Пояснення типів зв'язків

- Bayesian | - | -
- Limiting | - | -
- Specialcases | - | -
- Transformations | - | -
