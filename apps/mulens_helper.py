# all code from Tristan Blaineau
import numba as nb
import numpy as np
import pandas as pd
from sklearn.utils.random import sample_without_replacement
from iminuit import Minuit


@nb.njit
def mulens_simple(t, u0, t0, tE, mag):
	u = np.sqrt(u0*u0 + ((t-t0)**2)/tE/tE)
	amp = (u**2+2)/(u*np.sqrt(u**2+4))
	return - 2.5*np.log10(amp) + mag


@nb.njit
def nb_truncated_intrinsic_dispersion(time, mag, err, fraction=0.05):
	s0 = []
	for i in range(0, len(time)-2):
		ri = (time[i+1]-time[i])/(time[i+2]-time[i])
		sigmaisq = err[i+1]**2 + (1-ri)**2 * err[i]**2 + ri**2 * err[i+2]**2
		s0.append(((mag[i+1] - mag[i] - ri*(mag[i+2]-mag[i]))**2/sigmaisq))
	maxind = int(len(time)*fraction)+1
	s0 = np.array(s0)
	s0 = s0[s0.argsort()[:-maxind]].sum()
	return np.sqrt(s0/(len(time)-2-maxind))


@nb.njit
def to_minimize_simple_nd(params, t, tx, errx):
	"params : mags_1...mags_n, u0, t0, tE"
	u0 = params[-3]
	t0 = params[-2]
	tE = np.power(10, params[-1])
	s=0
	for j in range(len(params)-3):
		mag = params[j]
		#s+=loop4d_simple(mag, u0, t0, tE, t[j], tx[j], errx[j])
		for i in range(len(t[j])):
			s += (tx[j][i] - mulens_simple(t[j][i], u0, t0, tE, mag))**2/errx[j][i]**2
	return s


@nb.njit
def to_minimize_parallax_nd(params, t, tx, errx):
	"params : mags_1...mags_n, u0, t0, tE, du, theta"
	u0 = params[-5]
	t0 = params[-4]
	tE = params[-3]
	delta_u = params[-2]
	theta = params[-1]
	s=0
	for j in range(len(params)-5):
		mag = params[j]
		#s+=loop4d_parallax(mag, u0, t0, tE, delta_u, theta, t[j], tx[j], errx[j])
		for i in range(len(t[j])):
			s += (tx[j][i] - microlens_parallax(t[j][i], mag, 0, u0, t0, tE, delta_u, theta))**2/errx[j][i]**2
	return s


def latin_hypercube_sampling(bounds, pop):
	"""Latin Hypercube sampling to generate more uniformly distributed differential evolution initial parameters values.

	Parameters
	----------
	bounds : np.array
		Bounds to generate parameters within, should be of shape (nb of parameters, 2)
	pop : int
		Number of sets of inital parameters to generate
	"""
	ranges = np.linspace(bounds[:, 0], bounds[:, 1], pop + 1).T
	ranges = np.array([ranges[:,:-1], ranges[:,1:]]).T
	cs = np.random.uniform(low=ranges[:,:,0], high=ranges[:,:,1])
	a = sample_without_replacement(pop ** len(bounds), pop)
	a = np.array(np.unravel_index(a, [pop] * len(bounds)))
	return np.array([cs[a[i], i] for i in range(len(bounds))]).T


def diff_ev_lhs(func, times, data, errors, bounds, pop, recombination=0.7, tol=0.01):
	"""Compute minimum func value using differential evolution algorithm with input population generated using LHS"""
	init_pop = latin_hypercube_sampling(bounds, pop)
	return diff_ev_init_pop(func, times, data, errors, bounds, init_pop, recombination, tol)


fastmath = False


@nb.njit(fastmath=fastmath)
def inner_loop(x, a, b, c, dim, recombination, bounds):
	y = []
	for i in range(dim):
		ri = np.random.uniform(0, 1)
		temp = a[i] + np.random.uniform(0.5, 1.) * (b[i] - c[i])
		if ri < recombination:
			if bounds[i][0] < temp < bounds[i][1]:
				y.append(temp)
			else:
				y.append(np.random.uniform(bounds[i][0], bounds[i][1]))
		else:
			y.append(x[i])
	return y


@nb.njit(fastmath=fastmath)
def main_loop(func, times, data, errors, dim, recombination, init_pop, pop, all_values, best_idx, bounds):
	for i in range(pop):
		x = init_pop[i]
		idx = np.random.choice(pop, 2, replace=False)
		y = inner_loop(x, init_pop[best_idx], init_pop[idx[0]], init_pop[idx[1]], dim, recombination, bounds)
		cval = func(y, times, data, errors)
		if cval <= func(x, times, data, errors):
			all_values[i] = func(y, times, data, errors)
			init_pop[i] = y
		if cval < all_values[best_idx]:
			best_idx = i
	return best_idx


@nb.njit(fastmath=fastmath)
def diff_ev_init_pop(func, times, data, errors, bounds, init_pop, recombination=0.7, tol=0.01):
	"""
	Compute minimum func value using differential evolution algorithm with external input population

	Parameters
	----------
	func : function
		function to minimize, of format func(parameters, time, data, errors)
	times : sequence
		time values
	data : sequence
	errors : sequence
	bounds : np.array
		Limits of the parameter value to explore
		len(bounds) should be the number of parameters to func
	init_pop : int
		initial population
	recombination : float
		Recombination factor, fraction of non mutated specimen to next generation
		Should be in [0, 1]
	tol : float
		Tolerance factor, used for stopping condition

	Returns
	-------
	tuple(float, list, int)
		Returns minimum function value, corresponding parameters and number of loops

	"""
	dim = len(bounds)
	pop = len(init_pop)

	all_values = []
	for i in range(pop):
		all_values.append(func(init_pop[i], times, data, errors))
	all_values = np.array(all_values)
	best_idx = all_values.argmin()
	count = 0
	# loop
	while count < 1000:
		best_idx = main_loop(func, times, data, errors, dim, recombination, init_pop, pop, all_values, best_idx, bounds)
		count += 1

		if np.std(all_values) <= np.abs(np.mean(all_values)) * tol:
			break
	# rd = np.mean(all_values) - min_val
	# rd = rd**2/(min_val**2 + eps)
	# if rd<eps and count>20:
	#    break
	return all_values[best_idx], init_pop[best_idx], count


GLOBAL_COUNTER = 0
COLOR_FILTERS = {"r":{"mag":"mag_r", "err":"magerr_r"},
                 "g":{"mag":"mag_g", "err":"magerr_g"}}
#color filters defined for ZTF DR2


def fit_ml_de_simple(subdf, do_cut=False):
	"""Fit on one star

	Color filter names must be stocked in a COLOR_FILTERS dictionnary
	for example : COLOR_FILTERS = {"r":{"mag":"mag_r", "err":"magerr_r"},
                 				   "g":{"mag":"mag_g", "err":"magerr_g"}}

	Parameters
	----------
	subdf : pd.DataFrame
		Lightcurve data. Should have magnitudes stocked in "mag_*color*"  columns, magnitude errors in "magerr_*color*",
		for each *color* name and timestamps in "time" column

	do_cut : bool
		If True, clean aberrant points using distance from median of 5 points (default: {False})

	Returns
	-------
	pd.Series
		Contains parameters for the microlensing and flat curve fits, their chi2, informations on the fitter (fmin) and dof :

		mulens Fit results parameters : mag_1, ... mag_n, u0, t0, tE
		mulens Minuit fit output informations
		mulens Fit final Chi^2
		flat Fit results parameters : mag_1, ... mag_n
		flat Minuit fit output informations
		flat Fit final Chi^2
		Number of points used in each color filter
		Individual final mulens fit chi^2 value for each filter
		Individual final flat fit chi^2 value for each filter
		Intrinsic dispersion for each color filter
	"""

	# print(subdf.name)

	ufilters = subdf.filtercode.unique()

	mask = dict()
	errs = dict()
	mags = dict()
	cut5 = dict()
	time = dict()

	min_err = 0.0
	remove_extremities = False
	tolerance_ratio = 0.9
	p = True

	for key in ufilters:
		mask[key] = subdf["mag_" + key].notnull() & subdf["magerr_" + key].notnull() & subdf["magerr_" + key].between(
			min_err, 9.999, inclusive=False)  # No nan and limits on errors
		mags[key] = subdf[mask[key]]["mag_" + key]  # mags
		errs[key] = subdf[mask[key]]["magerr_" + key]  # errs
		cut5[key] = np.abs((mags[key].rolling(5, center=True).median() - mags[key][2:-2])) / errs[key][2:-2] < 5

		if not remove_extremities:
			cut5[key][:2] = True
			cut5[key][-2:] = True

		p *= cut5[key].sum() / len(cut5[key]) < tolerance_ratio

	if do_cut and not p:
		for key in ufilters:
			time[key] = subdf[mask[key] & cut5[key]].time.to_numpy()
			errs[key] = errs[key][cut5[key]].to_numpy()
			mags[key] = mags[key][cut5[key]].to_numpy()
	else:
		for key in ufilters:
			time[key] = subdf[mask[key]].time.to_numpy()
			errs[key] = errs[key].to_numpy()
			mags[key] = mags[key].to_numpy()

	# Normalize errors
	intrinsic_dispersion = dict()
	for key in COLOR_FILTERS.keys():
		intrinsic_dispersion[key] = np.nan
	for key in ufilters:
		if len(mags[key]) <= 3:
			intrinsic_dispersion[key] = 1.
		else:
			intrinsic_dispersion[key] = nb_truncated_intrinsic_dispersion(time[key], mags[key], errs[key],
																		  fraction=0.05)
			errs[key] = errs[key] * intrinsic_dispersion[key]

	# if magRE.size==0 or magBE.size==0 or magRM.size==0 or magBM.size==0:
	# 	return pd.Series(None)

	# flat fit
	def least_squares_flat(x):
		s = 0
		for idx, key in enumerate(ufilters):
			s += np.sum(((mags[key] - x[idx]) / errs[key]) ** 2)
		return s

	start = [np.median(mags[key]) for key in ufilters]
	error = [1. for _ in ufilters]
	name = ["f_magStar_" + key for key in ufilters]
	m_flat = Minuit.from_array_func(least_squares_flat,
									start=start,
									error=error,
									name=name,
									errordef=1,
									print_level=0)
	m_flat.migrad()
	global GLOBAL_COUNTER
	GLOBAL_COUNTER += 1
	# print(str(GLOBAL_COUNTER) + " : " + subdf.name)
	flat_params = m_flat.values

	# init for output
	flat_keys = ["f_magStar_" + key for key in COLOR_FILTERS.keys()]
	flat_values = []
	for key in COLOR_FILTERS.keys():
		if key in ufilters:
			flat_values.append(m_flat.values["f_magStar_" + key])
		else:
			flat_values.append(np.nan)
	flat_fmin = m_flat.get_fmin()
	flat_fval = m_flat.fval


	alltimes = np.concatenate(list(time.values()))
	bounds_simple = np.array([[-10, 30] for _ in ufilters] + [[0, 1], [alltimes.min(), alltimes.max()], [0, 3]])
	fval, pms, nbloops = diff_ev_lhs(to_minimize_simple_nd, list(time.values()), list(mags.values()),
									 list(errs.values()), bounds=bounds_simple, pop=70, recombination=0.3)

	names = ["u0", "t0", "tE"] + ["magStar_" + key for key in COLOR_FILTERS.keys()]
	micro_keys = names

	pms = list(pms)

	def least_squares_microlens(x):
		lsq = 0
		for idx, key in enumerate(ufilters):
			lsq += np.sum(((mags[key] - mulens_simple(time[key], x[0], x[1], x[2], x[idx + 3])) / errs[key]) ** 2)
		return lsq

	start = pms[-3:-1] + [np.power(10, pms[-1])] + pms[:-3]
	names = ["u0", "t0", "tE"] + ["magStar_" + key for key in ufilters]
	errors = [0.1, 100, 10] + [2 for key in ufilters]
	limits = [(0, 2), (2358940, 2558940), (1, 800)] + [(None, None) for key in ufilters]
	m_micro = Minuit.from_array_func(least_squares_microlens,
									 start=start,
									 error=errors,
									 limit=limits,
									 name=names,
									 errordef=1,
									 print_level=0)

	m_micro.migrad()
	micro_params = m_micro.values; print('#', micro_params)
	try:
		m_micro.minos()
		micro_minos_errors = m_micro.np_merrors(); print('##', micro_minos_errors)
	except RuntimeError:
		print("Migrad did not converge properly on star " + str(subdf.name))
		micro_minos_errors = np.nan
	lsqs = []
	micro_values = [micro_params['u0'], micro_params['t0'], micro_params['tE']]
	for key in COLOR_FILTERS.keys():
		if key in ufilters:
			lsqs.append(np.sum(((mags[key] - mulens_simple(time[key], micro_params['u0'], micro_params['t0'],
														   micro_params['tE'], micro_params["magStar_" + key])) /
								errs[key]) ** 2))
			micro_values.append(m_micro.values["magStar_" + key])
		else:
			lsqs.append(np.nan)
			micro_values.append(np.nan)
	micro_fmin = m_micro.get_fmin()
	micro_fval = m_micro.fval

	counts = []
	flat_chi2s = []
	median_errors = []
	for key in COLOR_FILTERS.keys():
		if key in ufilters:
			counts.append((~np.isnan(mags[key])).sum())
			flat_chi2s.append(np.sum(((mags[key] - flat_params[0]) / errs[key]) ** 2))
			median_errors.append(np.median(errs[key]))
		else:
			counts.append(0)
			flat_chi2s.append(np.nan)
			median_errors.append(np.nan)

	return pd.Series(
		micro_values + [micro_fmin, micro_fval] + [micro_minos_errors]
		+
		flat_values + [flat_fmin, flat_fval]
		+ counts
		+ lsqs
		+ flat_chi2s
		+ median_errors
		+ list(intrinsic_dispersion.values())

		,

		index=micro_keys + ['micro_fmin', 'micro_fval'] + ["micro_minos_errors"]
			  +
			  flat_keys + ['flat_fmin', 'flat_fval']
			  + ["counts_" + key for key in
				 COLOR_FILTERS.keys()]  # ["counts_RE", "counts_BE", "counts_RM", "counts_BM"]
			  + ["micro_chi2_" + key for key in
				 COLOR_FILTERS.keys()]  # ['micro_chi2_RE', 'micro_chi2_BE', 'micro_chi2_RM', 'micro_chi2_BM']
			  + ["flat_chi2_" + key for key in
				 COLOR_FILTERS.keys()]  # ['flat_chi2_RE', 'flat_chi2_RM', 'flat_chi2_BE', 'flat_chi2_BM']
			  + ["magerr_" + key + "_median" for key, cf in
				 COLOR_FILTERS.items()]  # ['errRE_median', 'errBE_median', 'errRM_median', 'errBM_median']
			  + ["intr_disp_" + key for key in intrinsic_dispersion.keys()]
	)

