"""
This controls and connects to the individual readers.
"""

import pandas as pd
import pint
import cf_xarray
from cf_xarray.units import units
import pint_xarray
import pint_pandas
# from pint_xarray import unit_registry as ureg
import xarray as xr

pint_xarray.unit_registry = units

# from cf_xarray.units import units
from ioos_qc import qartod
from ioos_qc.config import QcConfig

import ocean_data_gateway as odg


# MAYBE SHOULD BE ABLE TO INITIALIZE THE CLASS WITH ONLY METADATA OR DATASET NAMES?
# to skip looking for the datasets


class Gateway(object):
    """
    Wraps together the individual readers in order to have a single way to
    search.

    Attributes
    ----------
    kwargs_all: dict
        Input keyword arguments that are not specific to one of the readers.
        These may include "approach", "parallel", "kw" containing the time and
        space region to search for, etc.
    kwargs: dict
        Keyword arguments that contain specific arguments for the readers.
    """

    def __init__(self, **kwargs):
        """
        Parameters
        ----------
        kw: dict
          Contains space and time search constraints: `min_lon`, `max_lon`,
          `min_lat`, `max_lat`, `min_time`, `max_time`.
        approach: string
            approach is defined as 'stations' or 'region' depending on user
            choice.
        parallel: boolean, optional
            If True, run with simple parallelization using `multiprocessing`.
            If False, run serially. True by default. If input in this manner,
            the same value is used for all readers. If input by individual
            reader dictionary, the value can vary by reader.
        readers: ocean_data_gateway Reader, list of readers, optional
            Use this to use fewer than the full set of readers. For example,
            `readers=odg.erddap` or to specifically include all by name
            `readers = [odg.ErddapReader, odg.axdsReader, odg.localReader]`.
        erddap: dict, optional
            Dictionary of reader specifications. For example,
            `erddap={'known_server': 'ioos'}`. See odg.erddap.ErddapReader for
            more input options.
        axds: dict, optional
            Dictionary of reader specifications. For example,
            `axds={'axds_type': 'platform2'}`. See odg.axds.AxdsReader for
            more input options.
        local: dict, optional
            Dictionary of reader specifications. For example,
            `local={'filenames': filenames}` for a list of filenames.
            See odg.local.LocalReader for more input options.

        Notes
        -----
        To select search variables, input the variable names to each reader
        individually in the format `erddap={'variables': [list of variables]}`.
        Make sure that the variable names are correct for each individual
        reader. Check individual reader docs for more information.

        Input keyword arguments that are not specific to one of the readers will be collected in local dictionary kwargs_all. These may include "approach", "parallel", "kw" containing the time and space region to search for, etc.

        Input keyword arguments that are specific to readers will be collected
        in local dictionary kwargs.
        """

        # make sure only known keys are input in kwargs
        unknown_keys = set(list(kwargs.keys())) - set(odg.keys_kwargs)
        assertion = f"keys into Gateway {unknown_keys} are unknown."
        assert len(unknown_keys) == 0, assertion

        # set up a dictionary for general input kwargs
        exclude_keys = ["erddap", "axds", "local"]
        kwargs_all = {
            k: kwargs[k] for k in set(list(kwargs.keys())) - set(exclude_keys)
        }

        self.kwargs_all = kwargs_all

        # default approach is region
        if "approach" not in self.kwargs_all:
            self.kwargs_all["approach"] = "region"

        assertion = '`approach` has to be "region" or "stations"'
        assert self.kwargs_all["approach"] in ["region", "stations"], assertion

        # if "kw" not in self.kwargs_all:
        #     kw = {
        #         "min_lon": -124.0,
        #         "max_lon": -122.0,
        #         "min_lat": 38.0,
        #         "max_lat": 40.0,
        #         "min_time": "2021-4-1",
        #         "max_time": "2021-4-2",
        #     }
        #     self.kwargs_all["kw"] = kw

        self.kwargs = kwargs
        self.sources

    @property
    def sources(self):
        """Set up data sources (readers).

        Notes
        -----
        All readers are included by default (readers as listed in odg._SOURCES). See
         __init__ for options.
        """

        if not hasattr(self, "_sources"):

            # allow user to override what readers to use
            if "readers" in self.kwargs_all.keys():
                SOURCES = self.kwargs_all["readers"]
                if not isinstance(SOURCES, list):
                    SOURCES = [SOURCES]
            else:
                SOURCES = odg._SOURCES

            # loop over data sources to set them up
            sources = []
            for source in SOURCES:
                #                 print(source.reader)

                # in case of important options for readers
                # but the built in options are ignored for a reader
                # if one is input in kwargs[source.reader]
                if source.reader in odg.OPTIONS.keys():
                    reader_options = odg.OPTIONS[source.reader]
                    reader_key = list(reader_options.keys())[0]
                    # if the user input their own option for this, use it instead
                    # this makes it loop once
                    if (source.reader in self.kwargs.keys()) and (
                        reader_key in self.kwargs[source.reader]
                    ):
                        #                         reader_values = [None]
                        reader_values = self.kwargs[source.reader][reader_key]
                    else:
                        reader_values = list(reader_options.values())[0]
                else:
                    reader_key = None
                    # this is to make it loop once for cases without
                    # extra options like localReader
                    reader_values = [None]
                if not isinstance(reader_values, list):
                    reader_values = [reader_values]

                # catch if the user is putting in a set of variables to match
                # the set of reader options
                if (source.reader in self.kwargs) and (
                    "variables" in self.kwargs[source.reader]
                ):
                    variables_values = self.kwargs[source.reader]["variables"]
                    if not isinstance(variables_values, list):
                        variables_values = [variables_values]
                #                     if len(reader_values) == variables_values:
                #                         variables_values
                else:
                    variables_values = [None] * len(reader_values)

                # catch if the user is putting in a set of dataset_ids to match
                # the set of reader options
                if (source.reader in self.kwargs) and (
                    "dataset_ids" in self.kwargs[source.reader]
                ):
                    dataset_ids_values = self.kwargs[source.reader]["dataset_ids"]
                    if not isinstance(dataset_ids_values, list):
                        dataset_ids_values = [dataset_ids_values]
                #                     if len(reader_values) == variables_values:
                #                         variables_values
                else:
                    dataset_ids_values = [None] * len(reader_values)

                for option, variables, dataset_ids in zip(
                    reader_values, variables_values, dataset_ids_values
                ):
                    # setup reader with kwargs for that reader
                    # prioritize input kwargs over default args
                    # NEED TO INCLUDE kwargs that go to all the readers
                    args = {}
                    args_in = {
                        **args,
                        **self.kwargs_all,
                        #                                reader_key: option,
                        #                                **self.kwargs[source.reader],
                    }

                    if source.reader in self.kwargs.keys():
                        args_in = {
                            **args_in,
                            **self.kwargs[source.reader],
                        }

                    args_in = {**args_in, reader_key: option}

                    # deal with variables separately
                    args_in = {
                        **args_in,
                        "variables": variables,
                    }

                    # deal with dataset_ids separately
                    args_in = {
                        **args_in,
                        "dataset_ids": dataset_ids,
                    }

                    if self.kwargs_all["approach"] == "region":
                        reader = source.region(args_in)
                    elif self.kwargs_all["approach"] == "stations":
                        reader = source.stations(args_in)

                    sources.append(reader)

            self._sources = sources

        return self._sources

    @property
    def dataset_ids(self):
        """Find dataset_ids for each source/reader.

        Returns
        -------
        A list of dataset_ids where each entry in the list corresponds to one source/reader, which in turn contains a list of dataset_ids.
        """

        if not hasattr(self, "_dataset_ids"):

            dataset_ids = []
            for source in self.sources:

                dataset_ids.append(source.dataset_ids)

            self._dataset_ids = dataset_ids

        return self._dataset_ids

    @property
    def meta(self):
        """Find and return metadata for datasets.

        Returns
        -------
        A list with an entry for each reader. Each entry in the list contains a pandas DataFrames of metadata for that reader.

        Notes
        -----
        This is done by querying each data source function for metadata and
        then using the metadata for quick returns.

        This will not rerun if the metadata has already been found.

        Different sources have different metadata, though certain attributes
        are always available.

        TO DO: SEPARATE DATASOURCE FUNCTIONS INTO A PART THAT RETRIEVES THE
        DATASET_IDS AND METADATA AND A PART THAT READS IN THE DATA.
        """

        if not hasattr(self, "_meta"):

            # loop over data sources to read in metadata
            meta = []
            for source in self.sources:

                meta.append(source.meta)

            self._meta = meta

        return self._meta

    @property
    def data(self):
        """Return the data, given metadata.

        Notes
        -----
        This is either done in parallel with the `multiprocessing` library or
        in serial.
        """

        if not hasattr(self, "_data"):

            # loop over data sources to read in data
            data = []
            for source in self.sources:

                data.append(source.data)

            self._data = data

        return self._data

    def qc(self):
        """Light quality check on data.

        This runs one IOOS QARTOD on data as a first order quality check.
        Only returns data that is quality checked.

        Requires pint for unit handling.

        This is slow if your data is both chunks of time and space, so this
        should first narrow by both as much as possible.
        """

        # loop over data in sources, so one per source in the list
        data_out = []
        for data in self.data:
            for dataset_id, dd in data.items():

                # # This seems prohibitively slow for Datasets at least for now
                # if isinstance(dd, xr.Dataset):
                #     continue

                if isinstance(dd, pd.DataFrame):
                    cols = list(list(zip(*dd.columns))[0])
                elif isinstance(dd, xr.Dataset):
                    cols = list(dd.cf.standard_names.keys())

                import pdb; pdb.set_trace()
                varnames = odg.match_var(cols, list(odg.var_def.keys()))
                # import pdb; pdb.set_trace()
                # only proceed with var dict entries that have values, and just one entry
                varnames = {k: v[0] for k, v in varnames.items() if v}

                # for Datasets, replace varnames values (which are standard_names)
                # with their variable names to be eaier to work with
                if isinstance(dd, xr.Dataset):
                    for gen_name, dd_name in varnames.items():
                        dd_name_new = list(
                            dd.filter_by_attrs(standard_name=dd_name).data_vars.keys()
                        )[0]
                        varnames[gen_name] = dd_name_new

                # subset to just the boem or requested variables for each df or ds
                # import pdb; pdb.set_trace()
                # if isinstance(dd, pd.DataFrame):
                    # dd2 = dd[list(varnames.values())]
                # elif isinstance(dd, xr.Dataset):
                dd2 = dd[list(varnames.values())]

                # Preprocess to change salinity units away from 1e-3
                if isinstance(dd, pd.DataFrame):
                    # this replaces units in the 2nd column level of 1e-3 with psu
                    new_levs = ['psu' if col=='1e-3' else col for col in dd2.columns.levels[1]]
                    dd2.columns.set_levels(new_levs, level=1, inplace=True)
                elif isinstance(dd, xr.Dataset):
                    for Var in dd2.data_vars:
                        if 'units' in dd2[Var].attrs and dd2[Var].attrs['units']=='1e-3':
                            dd2[Var].attrs['units'] = 'psu'
                # run pint quantify on each data structure
                # import pdb; pdb.set_trace()
                dd2 = dd2.pint.quantify()
                # dd2 = dd2.pint.quantify(level=-1)

                # go through each variable by name to make sure in correct units
                # have to do this in separate loop so that can dequantify afterward
                for gen_name, dd_name in varnames.items():

                    # convert to conventional units
                    # only change units if they aren't already correct
                    if dd2[dd_name].pint.units != odg.var_def[gen_name]["units"]:
                        # this is super slow for Datasets since not local
                        dd2[dd_name] = dd2[dd_name].pint.to(
                            odg.var_def[gen_name]["units"]
                        )

                dd2 = dd2.pint.dequantify()

                # now loop for QARTOD on each variable
                for gen_name, dd_name in varnames.items():
                    # run QARTOD
                    qc_config = {
                        "qartod": {
                            "gross_range_test": {
                                "fail_span": odg.var_def[gen_name]["fail_span"],
                                "suspect_span": odg.var_def[gen_name]["suspect_span"],
                            },
                        }
                    }
                    qc = QcConfig(qc_config)
                    qc_results = qc.run(inp=dd2[dd_name])

                    # put flags into dataset
                    if isinstance(dd, pd.DataFrame):
                        dd2[f"{dd_name}_qc"] = qc_results["qartod"]["gross_range_test"]
                    elif isinstance(dd, xr.Dataset):
                        new_data = qc_results["qartod"]["gross_range_test"]
                        dims = dd2[dd_name].dims
                        dd2[f"{dd_name}_qc"] = (dims, new_data)
                data[dataset_id] = dd2
            data_out.append(data)

        return data_out
