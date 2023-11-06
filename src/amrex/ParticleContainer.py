"""
This file is part of pyAMReX

Copyright 2023 AMReX community
Authors: Axel Huebl
License: BSD-3-Clause-LBNL
"""


def pc_to_df(self, local=True, comm=None, root_rank=0):
    """
    Copy all particles into a pandas.DataFrame

    Parameters
    ----------
    self : amrex.ParticleContainer_*
        A ParticleContainer class in pyAMReX
    local : bool
        MPI-local particles
    comm : MPI Communicator
        if local is False, this defaults to mpi4py.MPI.COMM_WORLD
    root_rank : MPI root rank to gather to
        if local is False, this defaults to 0

    Returns
    -------
    A concatenated pandas.DataFrame with particles from all levels.

    Returns None if no particles were found.
    If local=False, then all ranks but the root_rank will return None.
    """
    import pandas as pd

    # create a DataFrame per particle box and append it to the list of
    # local DataFrame(s)
    dfs_local = []
    for lvl in range(self.finest_level + 1):
        for pti in self.const_iterator(self, level=lvl):
            if pti.size == 0:
                continue

            if self.is_soa_particle:
                next_df = pd.DataFrame()
            else:
                # AoS
                aos_np = pti.aos().to_numpy(copy=True)
                next_df = pd.DataFrame(aos_np)
                next_df.set_index("cpuid")
                next_df.index.name = "cpuid"

            # SoA
            soa_view = pti.soa().to_numpy(copy=True)
            soa_np_real = soa_view.real
            soa_np_int = soa_view.int

            for idx, array in enumerate(soa_np_real):
                next_df[f"SoA_real_{idx}"] = array
            for idx, array in enumerate(soa_np_int):
                next_df[f"SoA_int_{idx}"] = array

            dfs_local.append(next_df)

    # MPI Gather to root rank if requested
    if local:
        if len(dfs_local) == 0:
            df = None
        else:
            df = pd.concat(dfs_local)
    else:
        from mpi4py import MPI

        if comm is None:
            comm = MPI.COMM_WORLD
        rank = comm.Get_rank()

        # a list for each rank's list of DataFrame(s)
        df_list_list = comm.gather(dfs_local, root=root_rank)

        if rank == root_rank:
            flattened_list = [df for sublist in df_list_list for df in sublist]

            if len(flattened_list) == 0:
                df = pd.DataFrame()
            else:
                df = pd.concat(flattened_list, ignore_index=True)
        else:
            df = None

    return df


def register_ParticleContainer_extension(amr):
    """ParticleContainer helper methods"""
    import inspect
    import sys

    # register member functions for every ParticleContainer_* type
    for _, ParticleContainer_type in inspect.getmembers(
        sys.modules[amr.__name__],
        lambda member: inspect.isclass(member)
        and member.__module__ == amr.__name__
        and member.__name__.startswith("ParticleContainer_"),
    ):
        ParticleContainer_type.to_df = pc_to_df