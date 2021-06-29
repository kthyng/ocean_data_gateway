import cf_xarray
import numpy as np
import pint_xarray

# import ocean_data_gateway as odg
import xarray as xr

from cf_xarray.units import units


pint_xarray.unit_registry = units


def test_units():
    ds = xr.Dataset()
    ds["salt"] = ("dim", np.arange(10), {"units": "psu"})
    ds["lat"] = ("dim", np.arange(10), {"units": "degrees_north"})
    assert ds.pint.quantify()


# def test_QC():
#     ds = xr.Dataset()
#     ds["salt"] = ("dim", np.arange(10), {"units": "psu"})
#     assert ds.pint.quantify()
