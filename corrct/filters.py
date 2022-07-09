# -*- coding: utf-8 -*-
"""
Filtered back-projection filters.

@author: Nicola VIGANÒ, Computational Imaging group, CWI, The Netherlands,
and ESRF - The European Synchrotron, Grenoble, France
"""

import numpy as np

import skimage.transform as skt

from .operators import BaseTransform
from .utils_proc import get_circular_mask

from typing import Union, Sequence, Optional
from numpy.typing import ArrayLike, DTypeLike, NDArray

from abc import ABC, abstractmethod


class Filter(ABC):
    """Base FBP filter."""

    fbp_filter: NDArray[np.floating]
    pad_mode: str
    use_rfft: bool
    dtype: DTypeLike

    def __init__(
        self,
        fbp_filter: Union[ArrayLike, NDArray[np.floating], None],
        pad_mode: str,
        use_rfft: bool,
        dtype: DTypeLike,
    ) -> None:
        """Initialize Base FBP filter.

        Parameters
        ----------
        fbp_filter : Union[ArrayLike, NDArray[np.floating], None]
            The filter.
        pad_mode : str
            The padding mode.
        use_rfft : bool
            Whethert to use the `rfft` or complex `fft`.
        dtype : DTypeLike
            The data type of the filter.
        """
        self.dtype = dtype
        self.pad_mode = pad_mode.lower()
        self.use_rfft = use_rfft

        if fbp_filter is None:
            self.fbp_filter = np.array([1.0], dtype=dtype)
        else:
            self.fbp_filter = np.array(fbp_filter, dtype=dtype)

    def get_padding_size(self, data_wu_shape: Sequence[int]) -> int:
        """Compute the projection padding size for a linear convolution.

        Parameters
        ----------
        data_wu_shape : Sequence[int]
            The shape of the data

        Returns
        -------
        int
            The padding size of the last dimension.
        """
        return max(64, int(2 ** np.ceil(np.log2(2 * data_wu_shape[-1]))))

    @property
    def filter_fourier(self) -> NDArray[np.floating]:
        """Fourier representation of the filter.

        Returns
        -------
        NDArray[np.floating]
            The filter in Fourier.
        """
        return self.fbp_filter.copy()

    @property
    def filter_real(self) -> NDArray[np.floating]:
        """Real-space representation of the filter.

        Returns
        -------
        NDArray[np.floating]
            The filter in real-space.
        """
        if self.use_rfft:
            fbp_filter_r = np.fft.irfft(self.fbp_filter, axis=-1)
        else:
            fbp_filter_r = np.fft.ifft(self.fbp_filter, axis=-1).real
        return np.fft.fftshift(fbp_filter_r)

    def apply_filter(self, data_wu: NDArray, fbp_filter: Optional[NDArray] = None) -> NDArray:
        """Apply the filter to the data_wu.

        Parameters
        ----------
        data_wu : NDArray
            The sinogram.
        fbp_filter : NDArray, optional
            The filter to use. The default is None

        Returns
        -------
        NDArray
            The filtered sinogram.
        """
        data_wu_shape = data_wu.shape
        if fbp_filter is None:
            local_filter = self.fbp_filter
        else:
            local_filter = fbp_filter

        prj_size_pad = self.get_padding_size(data_wu_shape)

        pad_edge_u = (prj_size_pad - data_wu_shape[-1]) / 2
        pad_width = np.zeros((len(data_wu_shape), 2), dtype=int)
        pad_width[-1, :] = (int(np.ceil(pad_edge_u)), int(np.floor(pad_edge_u)))

        prj_pad = np.pad(data_wu, pad_width=tuple(pad_width), mode=self.pad_mode)  # type: ignore
        prj_pad = np.roll(prj_pad, shift=-pad_width[-1][0], axis=-1)

        local_filter = np.array(local_filter, ndmin=len(data_wu_shape))

        if self.use_rfft:
            prj_f = np.fft.rfft(prj_pad, axis=-1)
        else:
            prj_f = np.fft.fft(prj_pad, axis=-1)

        prj_f *= local_filter

        if self.use_rfft:
            prj_f = np.fft.irfft(prj_f, axis=-1)[..., : data_wu_shape[-1]]
        else:
            prj_f = np.fft.ifft(prj_f, axis=-1)[..., : data_wu_shape[-1]].real

        return prj_f

    @abstractmethod
    def compute_filter(self, data_wu: NDArray) -> None:
        """Compute the FBP filter for the given data.

        Parameters
        ----------
        data_wu : NDArray
            The reference sinogram / projection data.
        """

    def __call__(self, data_wu: NDArray) -> NDArray:
        """Filter the sinogram, by first computing the filter, and then applying it.

        Parameters
        ----------
        data_wu : NDArray
            The unfiltered sinogram.

        Returns
        -------
        NDArray
            The filtered sinogram.
        """
        self.compute_filter(data_wu)
        return self.apply_filter(data_wu, self.fbp_filter)


class FilterCustom(Filter):
    """Custom FBP filter."""

    def __init__(
        self,
        fbp_filter: Union[ArrayLike, NDArray[np.floating], None],
        pad_mode: str = "constant",
        use_rfft: bool = True,
        dtype: DTypeLike = np.float32,
    ) -> None:
        """Initialize Custom FBP filter.

        Parameters
        ----------
        fbp_filter : Union[ArrayLike, NDArray[np.floating], None]
            The filter.
        pad_mode : str, optional
            The padding mode, by default "constant".
        use_rfft : bool, optional
            Whethert to use the `rfft` or complex `fft`, by default True.
        dtype : DTypeLike, optional
            The data type of the filter, by default np.float32.
        """
        super().__init__(fbp_filter, pad_mode, use_rfft, dtype)

    def compute_filter(self, data_wu: NDArray) -> None:
        """Provide dummy implementation, because it is not required."""


class FilterFBP(Filter):
    """Traditional FBP filter."""

    filter_name: str

    def __init__(
        self, filter_name: str = "ramp", pad_mode: str = "constant", use_rfft: bool = True, dtype: DTypeLike = np.float32
    ) -> None:
        """Initialize traditional FBP filter.

        Parameters
        ----------
        filter_name : str
            The filter name
        use_rfft : bool, optional
            Whethert to use the `rfft` or complex `fft`, by default True
        dtype : DTypeLike, optional
            The type of the filter, by default np.float32
        """
        super().__init__(fbp_filter=None, pad_mode=pad_mode, use_rfft=use_rfft, dtype=dtype)

        self.filter_name = filter_name.lower()

    def compute_filter(self, data_wu: NDArray) -> None:
        """Compute the traditional FBP filter for the given data.

        Parameters
        ----------
        data_wu : NDArray
            The reference sinogram / projection data.
        """
        prj_size_pad = self.get_padding_size(data_wu.shape)

        self.fbp_filter = skt.radon_transform._get_fourier_filter(prj_size_pad, self.filter_name)
        self.fbp_filter = np.squeeze(self.fbp_filter) * np.pi / (2 * data_wu.shape[-2])

        if self.use_rfft:
            self.fbp_filter = self.fbp_filter[: (self.fbp_filter.shape[-1]) // 2 + 1]


class FilterMR(Filter):
    """Data dependent FBP filter.

    This is a simplified implementation from:

    [1] Pelt, D. M., & Batenburg, K. J. (2014). Improving filtered backprojection
    reconstruction by data-dependent filtering. Image Processing, IEEE
    Transactions on, 23(11), 4750-4762.

    Code inspired by: https://github.com/dmpelt/pymrfbp
    """

    projector: BaseTransform

    binning_type: str
    binning_start: Union[int, None]

    lambda_smooth: Union[float, None]

    is_initialized: bool

    def __init__(
        self,
        projector: BaseTransform,
        binning_type: str = "exponential",
        binning_start: Union[int, None] = 2,
        lambda_smooth: Optional[float] = None,
        pad_mode: str = "constant",
        use_rfft: bool = True,
        dtype: DTypeLike = np.float32,
    ) -> None:
        """Initialize data-driven FBP filter.

        Parameters
        ----------
        projector : BaseTransform
            The projector to use for handling the data.
        start_exp_binning : int, optional
            From which distance to start exponentional binning. The default is 2.
        lambda_smooth : float, optional
            Smoothing parameter. The default is None.
        dtype : DTypeLike, optional
            Filter data type. The default is np.float32.
        """
        super().__init__(fbp_filter=None, pad_mode=pad_mode, use_rfft=use_rfft, dtype=dtype)

        self.projector = projector

        self.binning_type = binning_type.lower()
        if self.binning_type not in ("exponential", "incremental"):
            raise ValueError("Binning type should be either 'exponential' or 'incremental'.")
        self.binning_start = binning_start
        self.lambda_smooth = lambda_smooth

        self.is_initialized = False

    def initialize(self, data_wu_shape: Sequence[int]) -> None:
        """Initialize filter.

        Parameters
        ----------
        data_wu_shape : Sequence[int]
            Shape of the data.
        """
        num_pad_pixels = self.get_padding_size(data_wu_shape)

        filter_positions = np.abs(np.fft.fftfreq(num_pad_pixels, 1 / num_pad_pixels))

        window_size = 1
        window_position = 0

        basis_r = []
        while window_position < filter_positions.max():
            basis_tmp = np.zeros(filter_positions.shape, dtype=self.dtype)

            binning_positions = np.logical_and(
                window_position <= filter_positions, filter_positions < (window_position + window_size)
            )
            basis_tmp[binning_positions] = 1.0

            basis_r.append(basis_tmp)
            window_position += window_size

            if self.binning_start is not None and window_position > self.binning_start:
                if self.binning_type == "exponential":
                    window_size = 2 * window_size
                else:
                    window_size += 1

        self.basis_r = np.array(basis_r, dtype=self.dtype)
        if self.use_rfft:
            self.basis_f = np.fft.rfft(self.basis_r, axis=-1).real
        else:
            self.basis_f = np.fft.fft(self.basis_f, axis=-1).real

        self.is_initialized = True

    def compute_filter(self, data_wu: NDArray) -> None:
        """Compute the filter.

        Parameters
        ----------
        data_wu : NDArray
            The sinogram.
        projector : ProjectorOperator
            The projector used in the FBP.
        """
        if not self.is_initialized:
            self.initialize(data_wu.shape)

        num_sino_pixels = data_wu.shape[-1]

        sino_size = data_wu.shape[-2] * num_sino_pixels
        nrows = sino_size
        ncols = self.basis_f.shape[-2]

        if self.lambda_smooth:
            grad_vol_size = num_sino_pixels * (num_sino_pixels - 1)
            nrows += 2 * grad_vol_size

        A = np.zeros((nrows, ncols), dtype=self.dtype)
        vol_mask = get_circular_mask([num_sino_pixels] * 2)

        for ii, bas_f in enumerate(self.basis_f):
            data_wu_f = self.apply_filter(data_wu, bas_f)

            img = self.projector.T(data_wu_f)
            img *= vol_mask

            A[:sino_size, ii] = self.projector(img).flatten()

            if self.lambda_smooth:
                dx = np.diff(img, axis=-2)
                dy = np.diff(img, axis=-1)
                d = np.concatenate((dx.flatten(), dy.flatten()))
                A[sino_size:, ii] = self.lambda_smooth * d

        b = np.zeros((nrows,), dtype=self.dtype)
        b[:sino_size] = data_wu.flatten()
        fitted_components = np.linalg.lstsq(A, b, rcond=None)[0].astype(self.dtype)

        self.fbp_filter = fitted_components.dot(self.basis_f)
