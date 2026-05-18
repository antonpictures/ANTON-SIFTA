#!/usr/bin/env python3
"""System/swarm_turbulence_substrate.py — atmospheric turbulence substrate.

Architect 2026-05-18:
    "Build a stigma app for FarSight. Point it at peace, protection,
    security — telescopes, search-and-rescue, dam inspection, wildlife
    re-ID. Same physics, lawful target."

Reference: Liu et al., "FarSight: A Physics-Driven Whole-Body Biometric
System at Large Distance and Altitude" (arXiv:2306.17206, 2023). We
borrow ONLY the physics of imaging through atmospheric turbulence —
not the person-recognition pipeline. The recognition head is replaced
upstream by ``swarm_sar_triage_organ.py``, which asks "is there a
target shape here?" instead of "who is this person?".

Doctrine boundary
=================

* §3.1 (Non-Proliferation): this module is dual-use turbulence physics.
  Anyone deploying it for mass surveillance / military biometrics is
  outside license. Lawful research, lawful SAR, lawful industrial
  safety, accident research, wildlife conservation, and adaptive-optics
  astronomy are explicitly permitted under §3.2.
* §3.3 (Receipt Integrity): every phase-screen realization is reachable
  through a deterministic ``(r0, L0, seed)`` triple, so swimmer
  hypotheses can be re-derived from receipts without storing the
  full screen.

Physics
-------

Atmospheric refractive-index fluctuations are characterized by the
**structure parameter** :math:`C_n^2` (units :math:`m^{-2/3}`). Typical
ranges (Liu et al. 2023, §1):

    weak turbulence   :math:`C_n^2 \\sim 10^{-17}`
    strong turbulence :math:`C_n^2 \\sim 10^{-14}`

For an imaging path of length :math:`L` and optical wavenumber
:math:`k = 2\\pi/\\lambda`, the **Fried parameter** :math:`r_0` (the
coherence length of the wavefront) is:

.. math::

    r_0 = \\left[ 0.423 \\, k^2 \\int_0^L C_n^2(z) \\, dz \\right]^{-3/5}

When :math:`C_n^2` is approximately constant over the path:

.. math::

    r_0 \\approx \\left[ 0.423 \\, k^2 \\, C_n^2 \\, L \\right]^{-3/5}

Smaller :math:`r_0` = worse seeing. Diffraction-limited imaging through
turbulence requires the aperture :math:`D \\lesssim r_0`; beyond that
the resolution stops improving with aperture size.

We use the **von Kármán phase-screen** model — a finite-outer-scale
refinement of Kolmogorov. Phase power spectral density:

.. math::

    \\Phi_\\varphi(\\kappa) = 0.023 \\, r_0^{-5/3} \\,
        (\\kappa^2 + \\kappa_0^2)^{-11/6} \\,
        \\exp(-\\kappa^2 / \\kappa_m^2)

with :math:`\\kappa_0 = 2\\pi/L_0` (outer scale) and
:math:`\\kappa_m = 5.92/l_0` (inner scale).

A phase screen realization is drawn as
:math:`\\varphi = \\mathcal{F}^{-1}[\\sqrt{\\Phi_\\varphi} \\cdot \\mathcal{N}(0,1)]`
on a regular grid. The point-spread function is then
:math:`h = |\\mathcal{F}[\\exp(i\\varphi) \\cdot P]|^2` where :math:`P`
is the pupil. The degraded image is :math:`I_{obs} = I_0 * h + n`.

Truth label: ``SIFTA_TURBULENCE_SUBSTRATE_V0``.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Optional, Tuple

import numpy as np

_TRUTH_LABEL = "SIFTA_TURBULENCE_SUBSTRATE_V0"

# Physical constants
_DEFAULT_WAVELENGTH_M = 550e-9       # green light, 550 nm
_DEFAULT_OUTER_SCALE_M = 100.0       # L0 = 100 m typical surface layer
_DEFAULT_INNER_SCALE_M = 5e-3        # l0 = 5 mm typical
_DEFAULT_PATH_LENGTH_M = 1000.0      # 1 km (Liu et al. test range)
_DEFAULT_APERTURE_M = 0.2            # 20 cm aperture
_DEFAULT_PUPIL_PITCH_M = 1.5625e-3   # pupil-plane sample pitch (aperture/128)
_DEFAULT_FOCAL_LENGTH_M = 0.5        # 50 cm focal length
# NOTE: "pixel_pitch_m" in this module means the PUPIL-PLANE sample
# spacing, NOT the sensor-plane (focal-plane) pixel pitch. They are
# different physical surfaces. Phase screens live in the pupil; the
# PSF then lives in the focal plane at λ·f/(N·pupil_pitch) per pixel.


@dataclass(frozen=True)
class TurbulenceParams:
    """Bundle of atmospheric + optical params for a single look.

    Attributes
    ----------
    cn2 : float
        Refractive index structure parameter, units m^(-2/3).
    wavelength_m : float
        Optical wavelength, meters.
    path_length_m : float
        Total propagation path, meters.
    outer_scale_m : float
        Von Kármán outer scale L0, meters.
    inner_scale_m : float
        Inner scale l0, meters.
    aperture_m : float
        Receiver aperture diameter, meters.
    """
    cn2: float
    wavelength_m: float = _DEFAULT_WAVELENGTH_M
    path_length_m: float = _DEFAULT_PATH_LENGTH_M
    outer_scale_m: float = _DEFAULT_OUTER_SCALE_M
    inner_scale_m: float = _DEFAULT_INNER_SCALE_M
    aperture_m: float = _DEFAULT_APERTURE_M

    @property
    def k(self) -> float:
        """Optical wavenumber, rad/m."""
        return 2.0 * math.pi / self.wavelength_m

    @property
    def r0(self) -> float:
        """Fried parameter (coherence length), meters.

        :math:`r_0 = [0.423 k^2 C_n^2 L]^{-3/5}`.
        """
        if self.cn2 <= 0.0:
            return float("inf")
        x = 0.423 * (self.k ** 2) * self.cn2 * self.path_length_m
        return x ** (-3.0 / 5.0)

    @property
    def seeing_arcsec(self) -> float:
        """Seeing FWHM, arcseconds (atmospheric only).

        :math:`\\theta = 0.98 \\lambda / r_0` in radians.
        """
        if self.r0 <= 0.0 or not math.isfinite(self.r0):
            return 0.0
        theta_rad = 0.98 * self.wavelength_m / self.r0
        return theta_rad * (180.0 / math.pi) * 3600.0


def r0_to_cn2(r0_m: float,
              *,
              wavelength_m: float = _DEFAULT_WAVELENGTH_M,
              path_length_m: float = _DEFAULT_PATH_LENGTH_M) -> float:
    """Invert the Fried parameter back to a constant-:math:`C_n^2` value.

    Useful for translating swimmer hypotheses (held in :math:`r_0`) to
    the :math:`C_n^2` reading we expose on the visible widget.
    """
    if r0_m <= 0.0 or not math.isfinite(r0_m):
        return 0.0
    k = 2.0 * math.pi / wavelength_m
    return (r0_m ** (-5.0 / 3.0)) / (0.423 * k * k * path_length_m)


def make_phase_screen(
    *,
    r0_m: float,
    grid: int = 128,
    pixel_pitch_m: float = _DEFAULT_PUPIL_PITCH_M,
    outer_scale_m: float = _DEFAULT_OUTER_SCALE_M,
    inner_scale_m: float = _DEFAULT_INNER_SCALE_M,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Draw one von Kármán phase-screen realization, radians.

    Returns a ``(grid, grid)`` float64 array of phase values.

    The PSD is sampled on a regular Fourier grid; a complex Gaussian is
    drawn, scaled by :math:`\\sqrt{\\Phi_\\varphi(\\kappa)}`, and inverse
    FFT'd. Standard Schmidt 2010 (Numerical Simulation of Optical Wave
    Propagation, SPIE) recipe.
    """
    rng = np.random.default_rng(seed)
    N = int(grid)

    # Fourier grid in cycles/m, then radians/m
    df = 1.0 / (N * pixel_pitch_m)
    fx = (np.arange(N) - N // 2) * df
    FX, FY = np.meshgrid(fx, fx, indexing="xy")
    kappa = 2.0 * math.pi * np.sqrt(FX * FX + FY * FY)

    kappa0 = 2.0 * math.pi / max(outer_scale_m, 1e-6)
    kappa_m = 5.92 / max(inner_scale_m, 1e-9)

    # Von Kármán PSD (radians^2 m^2)
    psd = (
        0.023
        * (r0_m ** (-5.0 / 3.0))
        * (kappa * kappa + kappa0 * kappa0) ** (-11.0 / 6.0)
        * np.exp(-(kappa * kappa) / (kappa_m * kappa_m))
    )
    # Kill DC (mean phase is unobservable; piston is not seeing)
    psd[N // 2, N // 2] = 0.0

    # Schmidt 2010 recipe: amplitude per Fourier bin =
    #     N^2 · 2π · df · sqrt(Phi)
    # so that the IFFT (with its built-in 1/N^2 factor) produces a
    # screen whose total variance matches the continuous PSD integral.
    dkappa = 2.0 * math.pi * df
    amplitude = (N * N) * dkappa * np.sqrt(psd)
    noise = (rng.standard_normal((N, N)) + 1j * rng.standard_normal((N, N))) / math.sqrt(2.0)
    spectrum = amplitude * noise
    # ifftshift before ifft because we built spectrum centered
    screen = np.fft.ifft2(np.fft.ifftshift(spectrum)).real

    # ----- Lane/Schmidt subharmonic patches -----
    # The base FFT grid under-samples low-kappa modes (Kolmogorov has
    # most variance near kappa=0). Add three octave-spaced subharmonic
    # passes at 1/3, 1/9, 1/27 of the base df, each on a coarse 3x3
    # grid centered on DC. This is the standard Lane-Whittaker-Cannon
    # 1992 correction implemented in Schmidt 2010 §9.5.
    yy_real, xx_real = np.indices((N, N))
    # Spatial coordinates relative to grid center (meters):
    x_m = (xx_real - N / 2.0) * pixel_pitch_m
    y_m = (yy_real - N / 2.0) * pixel_pitch_m

    for p in range(1, 4):
        # Subharmonic grid sample spacing: shrink df by factor 3^p
        df_sub = df / (3.0 ** p)
        dkappa_sub = 2.0 * math.pi * df_sub
        for i in (-1, 0, 1):
            for j in (-1, 0, 1):
                if i == 0 and j == 0:
                    continue
                fxs = i * df_sub
                fys = j * df_sub
                kappa_s = 2.0 * math.pi * math.sqrt(fxs * fxs + fys * fys)
                psd_s = (
                    0.023
                    * (r0_m ** (-5.0 / 3.0))
                    * (kappa_s * kappa_s + kappa0 * kappa0) ** (-11.0 / 6.0)
                    * math.exp(-(kappa_s * kappa_s) / (kappa_m * kappa_m))
                )
                amp_s = dkappa_sub * math.sqrt(max(psd_s, 0.0))
                c_re = rng.standard_normal() / math.sqrt(2.0)
                c_im = rng.standard_normal() / math.sqrt(2.0)
                phase_arg = 2.0 * math.pi * (fxs * x_m + fys * y_m)
                screen += amp_s * (c_re * np.cos(phase_arg) - c_im * np.sin(phase_arg))

    return screen.astype(np.float64)


def make_psf(
    *,
    phase_screen: np.ndarray,
    aperture_m: float = _DEFAULT_APERTURE_M,
    pixel_pitch_m: float = _DEFAULT_PUPIL_PITCH_M,
) -> np.ndarray:
    """Pupil-plane diffraction PSF from a phase screen.

    :math:`h = |\\mathcal{F}[\\exp(i\\varphi) \\cdot P]|^2`

    Returned PSF is normalized to unit sum. Useful for short-exposure
    (ms-scale) speckle simulation. For long-exposure averaged imagery
    use :func:`make_long_exposure_psf` instead.
    """
    N = phase_screen.shape[0]
    yy, xx = np.indices((N, N)) - N / 2.0
    r_pix = np.sqrt(xx * xx + yy * yy)
    pupil_radius_pix = (aperture_m / 2.0) / pixel_pitch_m
    pupil = (r_pix <= pupil_radius_pix).astype(np.float64)

    field = pupil * np.exp(1j * phase_screen)
    psf = np.abs(np.fft.fftshift(np.fft.fft2(field))) ** 2
    total = float(psf.sum())
    if total > 0:
        psf /= total
    return psf


def make_long_exposure_psf(
    *,
    r0_m: float,
    grid: int = 128,
    wavelength_m: float = _DEFAULT_WAVELENGTH_M,
    focal_length_m: float = _DEFAULT_FOCAL_LENGTH_M,
    sensor_pitch_m: float = 5e-6,
    moffat_beta: float = 3.5,
    seed: Optional[int] = None,
) -> np.ndarray:
    """Long-exposure atmospheric PSF (Moffat profile, r₀-parameterized).

    For exposures longer than the atmospheric coherence time
    (~1-10 ms), the PSF averages to a smooth profile well-fit by the
    Moffat 1969 form:

    .. math::

        h(r) = \\frac{\\beta - 1}{\\pi \\alpha^2}
               \\left[1 + (r/\\alpha)^2 \\right]^{-\\beta}

    with FWHM = :math:`2 \\alpha \\sqrt{2^{1/\\beta} - 1}`. The
    atmospheric seeing FWHM in radians is :math:`\\theta = 0.98
    \\lambda / r_0`; in focal-plane pixels it is :math:`\\theta \\cdot
    f / p_{sensor}`.

    Returned PSF is unit-sum (probability density), shape ``(grid, grid)``.
    ``seed`` is accepted for API symmetry with the speckle path but the
    long-exposure PSF is deterministic in :math:`r_0` (averaging removes
    the random realizations).
    """
    _ = seed  # unused, kept for signature parity with make_phase_screen path
    N = int(grid)
    if r0_m <= 0 or not math.isfinite(r0_m):
        # No turbulence → unit impulse at center
        psf = np.zeros((N, N), dtype=np.float64)
        psf[N // 2, N // 2] = 1.0
        return psf

    # Seeing FWHM in radians on the sky, then in focal-plane pixels
    theta_rad = 0.98 * wavelength_m / r0_m
    fwhm_pix = theta_rad * focal_length_m / sensor_pitch_m
    # Moffat α from FWHM and β:
    #   FWHM = 2α · sqrt(2^(1/β) - 1)
    alpha = max(fwhm_pix / (2.0 * math.sqrt(2.0 ** (1.0 / moffat_beta) - 1.0)), 1e-3)

    yy, xx = np.indices((N, N)) - N / 2.0
    r2 = xx * xx + yy * yy
    psf = (1.0 + r2 / (alpha * alpha)) ** (-moffat_beta)
    s = float(psf.sum())
    if s > 0:
        psf /= s
    return psf


def degrade(
    image: np.ndarray,
    *,
    params: TurbulenceParams,
    seed: Optional[int] = None,
    noise_sigma: float = 0.01,
    long_exposure: bool = True,
) -> Tuple[np.ndarray, np.ndarray]:
    """Forward atmospheric-turbulence degradation operator.

    Parameters
    ----------
    long_exposure : bool, default True
        If True, use the Moffat long-exposure averaged PSF (smooth,
        :math:`r_0`-parameterized — correct for >10 ms exposures from
        drones / fixed cameras / telescope long exposures). If False,
        use the speckle PSF :math:`|\\mathcal{F}[e^{i\\varphi}P]|^2`
        (correct for sub-ms exposures and lucky-imaging frames).

    Returns
    -------
    degraded_image : np.ndarray
    psf : np.ndarray
        The PSF used. Receipts can re-derive everything from
        :math:`(r_0, \\text{seed})` + this flag.
    """
    img = np.asarray(image, dtype=np.float64)
    if img.ndim != 2:
        raise ValueError("degrade() expects a 2-D image")

    if long_exposure:
        psf = make_long_exposure_psf(
            r0_m=params.r0,
            grid=img.shape[0],
            wavelength_m=params.wavelength_m,
            seed=seed,
        )
    else:
        screen = make_phase_screen(
            r0_m=params.r0,
            grid=img.shape[0],
            outer_scale_m=params.outer_scale_m,
            inner_scale_m=params.inner_scale_m,
            seed=seed,
        )
        psf = make_psf(
            phase_screen=screen,
            aperture_m=params.aperture_m,
        )

    # FFT convolution: pad to next power-of-2 isn't strictly needed for
    # equal-sized arrays, and we accept circular wraparound for speed.
    I_f = np.fft.fft2(img)
    H_f = np.fft.fft2(np.fft.ifftshift(psf))
    blurred = np.fft.ifft2(I_f * H_f).real

    if noise_sigma > 0.0:
        rng = np.random.default_rng(None if seed is None else seed + 1)
        blurred = blurred + rng.normal(0.0, noise_sigma, size=blurred.shape)

    return blurred, psf


def wiener_restore(
    degraded: np.ndarray,
    *,
    psf: np.ndarray,
    regularization: float = 5e-3,
) -> np.ndarray:
    """Wiener-like deconvolution given an estimated PSF.

    :math:`\\hat{I} = \\mathcal{F}^{-1}\\left[ \\frac{H^*}{|H|^2 + \\alpha} \\, \\mathcal{F}[I_{obs}] \\right]`

    This is the per-hypothesis reconstruction step a swimmer performs.
    Final swarm output averages reconstructions weighted by pheromone.
    """
    D_f = np.fft.fft2(np.asarray(degraded, dtype=np.float64))
    H_f = np.fft.fft2(np.fft.ifftshift(psf))
    denom = (np.abs(H_f) ** 2) + float(regularization)
    R_f = np.conj(H_f) / denom * D_f
    return np.fft.ifft2(R_f).real


# ---------------------------------------------------------------------------
# Synthetic ground-truth targets for the demo (no real surveillance imagery)
# ---------------------------------------------------------------------------

def synthetic_target(
    *,
    kind: str = "rescue_hiker",
    grid: int = 128,
) -> np.ndarray:
    """A simple, lawful-target binary scene.

    ``kind`` ∈ {
        "rescue_hiker"   — stylized human silhouette against a slope,
        "dam_wall"       — horizontal band with a vertical crack,
        "tower_array"    — three vertical poles (transmission line),
        "telescope_star" — point source on dark background,
        "zebra_stripes"  — diagonal stripe pattern (wildlife re-ID),
    }

    These are SYNTHETIC scenes used to demonstrate the physics. No
    real persons, no real surveillance imagery, no BRIAR data is
    used or required.
    """
    N = int(grid)
    img = np.zeros((N, N), dtype=np.float64)
    yy, xx = np.indices((N, N))

    if kind == "rescue_hiker":
        # Slope: linear ramp 0.15 to 0.35
        img += 0.15 + 0.20 * (yy / max(N - 1, 1))
        # Head
        cx, cy = N // 2, N // 3
        head_r = max(N // 24, 3)
        head = ((xx - cx) ** 2 + (yy - cy) ** 2) <= head_r * head_r
        img[head] = 0.90
        # Torso
        torso = (
            (np.abs(xx - cx) <= max(N // 22, 2))
            & (yy >= cy + head_r)
            & (yy <= cy + head_r + N // 4)
        )
        img[torso] = 0.85
        # Legs (two columns)
        leg_top = cy + head_r + N // 4
        leg_bot = min(leg_top + N // 5, N - 1)
        legL = (np.abs(xx - (cx - N // 60 - 1)) <= 1) & (yy >= leg_top) & (yy <= leg_bot)
        legR = (np.abs(xx - (cx + N // 60 + 1)) <= 1) & (yy >= leg_top) & (yy <= leg_bot)
        img[legL] = 0.80
        img[legR] = 0.80

    elif kind == "dam_wall":
        img += 0.45
        # Concrete band
        band = (yy >= N // 3) & (yy <= 2 * N // 3)
        img[band] = 0.80
        # Vertical crack
        crack = (np.abs(xx - N // 2) <= 1) & band
        img[crack] = 0.10

    elif kind == "tower_array":
        img += 0.20 + 0.10 * (yy / max(N - 1, 1))
        for cx in (N // 4, N // 2, 3 * N // 4):
            pole = (np.abs(xx - cx) <= 1) & (yy >= N // 5) & (yy <= 4 * N // 5)
            img[pole] = 0.95

    elif kind == "telescope_star":
        img += 0.05  # dark sky
        cx, cy = N // 2, N // 2
        star = ((xx - cx) ** 2 + (yy - cy) ** 2) <= 1
        img[star] = 1.0
        # A second, dimmer star
        img[(xx - (cx + N // 5)) ** 2 + (yy - (cy - N // 7)) ** 2 <= 1] = 0.6

    elif kind == "zebra_stripes":
        img += 0.85
        stripe = ((xx + yy) // max(N // 12, 1)) % 2 == 0
        img[stripe] = 0.10

    else:
        raise ValueError(f"unknown synthetic_target kind: {kind!r}")

    return np.clip(img, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Smoke test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys

    print(f"[{_TRUTH_LABEL}] sanity:")
    for cn2 in (1e-17, 1e-16, 1e-15, 1e-14):
        p = TurbulenceParams(cn2=cn2)
        print(
            f"  C_n^2={cn2:.0e}  r0={p.r0*100:.2f} cm  "
            f"seeing={p.seeing_arcsec:.2f}\""
        )

    img = synthetic_target(kind="rescue_hiker", grid=128)
    params = TurbulenceParams(cn2=5e-15)
    degraded, psf = degrade(img, params=params, seed=42)
    restored = wiener_restore(degraded, psf=psf)

    print(
        f"  forward: img range [{img.min():.2f}, {img.max():.2f}], "
        f"degraded range [{degraded.min():.2f}, {degraded.max():.2f}], "
        f"restored range [{restored.min():.2f}, {restored.max():.2f}]"
    )
    # Sanity: PSF energy preserved
    print(f"  psf sum = {psf.sum():.4f} (expect ~1.0)")
    sys.exit(0)
