// -*- C++ -*-

#if !defined(__numerical_random_PoissonGeneratorExpInvAc_ipp__)
#error This file is an implementation detail of PoissonGeneratorExpInvAc.
#endif

BEGIN_NAMESPACE_NUMERICAL


//! Threshhold for whether one should use the exponential inter-arrival method or the inversion method in computing a Poisson deviate.
template<typename T, class Generator>
class PdeiaExpVsInv {
public:
  //! Use the exponential inter-arrival method for means less than this value.
  static
  T
  getThreshhold() {
#ifdef NUMERICAL_POISSON_HERMITE_APPROXIMATION
    return 0.4;
#else
    return 2.0;
#endif
  }
};


//! Threshhold for whether one should use the inversion method or the acceptance-complement method in computing a Poisson deviate.
template<typename T, class Generator>
class PdeiaInvVsAc {
public:
  //! Use the inversion method for means less than this value.
  static
  T
  getThreshhold() {
#ifdef NUMERICAL_POISSON_HERMITE_APPROXIMATION
    return 13;
#else
    return 6.5;
#endif
  }
};


// Construct using the exponential generator and the normal generator.
template<typename T, 
	 class Uniform,
	 template<typename, class> class Exponential,
	 template<typename, class> class Normal>
inline
PoissonGeneratorExpInvAc<T, Uniform, Exponential, Normal>::
PoissonGeneratorExpInvAc(ExponentialGenerator* exponentialGenerator,
		       NormalGenerator* normalGenerator) :
  _exponentialInterArrival(exponentialGenerator),
#ifdef NUMERICAL_POISSON_HERMITE_APPROXIMATION
  _inversion(exponentialGenerator->getDiscreteUniformGenerator(),
	     PdeiaInvVsAc<T, Uniform>::getThreshhold()),
#else
  _inversion(exponentialGenerator->getDiscreteUniformGenerator()),
#endif
  _acceptanceComplementWinrand(normalGenerator)
{}



template<typename T, 
	 class Uniform,
	 template<typename, class> class Exponential,
	 template<typename, class> class Normal>
inline
typename PoissonGeneratorExpInvAc<T, Uniform, Exponential, Normal>::result_type
PoissonGeneratorExpInvAc<T, Uniform, Exponential, Normal>::
operator()(const argument_type mean) {
  // If the mean is very small, use the exponential inter-arrival method.
  if (mean < PdeiaExpVsInv<T, Uniform>::getThreshhold()) {
    return _exponentialInterArrival(mean);
  }
  // Use the inversion method for small means.
  if (mean < PdeiaInvVsAc<T, Uniform>::getThreshhold()) {
    return _inversion(mean);
  }
  // Use acceptance-complement for the rest.
  return _acceptanceComplementWinrand(mean);
}


END_NAMESPACE_NUMERICAL

// End of file.
