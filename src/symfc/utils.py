"""Functions to handle matrix indices."""
import itertools

import numpy as np
from scipy.sparse import coo_array, kron

from symfc.spg_reps import SpgReps


def get_spg_projector(spg_reps: SpgReps, decompr_idx: np.ndarray) -> coo_array:
    """Compute compact spg projector matrix using kron.

    This computes C.T @ spg_proj (kron_c) @ perm_proj @ C,
    where C is ``compression_mat``.

    """
    trans_perms = spg_reps.translation_permutations
    n_lp, N = trans_perms.shape
    compression_mat = get_lat_trans_compr_matrix(decompr_idx, N, n_lp)
    coset_reps_sum = _get_compr_coset_reps_sum(spg_reps)
    C_perm = get_perm_compr_matrix(N)
    perm = C_perm.T @ compression_mat
    perm = perm.T @ perm
    return coset_reps_sum @ perm


def _get_compr_coset_reps_sum(spg_reps: SpgReps):
    trans_perms = spg_reps.translation_permutations
    n_lp, N = trans_perms.shape
    size = N**2 * 9 // n_lp
    coset_reps_sum = coo_array(([], ([], [])), shape=(size, size), dtype="double")
    atomic_decompr_idx = get_atomic_lat_trans_decompr_indices(trans_perms)
    C = coo_array(
        (
            np.ones(N**2, dtype=int),
            (np.arange(N**2, dtype=int), atomic_decompr_idx),
        ),
        shape=(N**2, N**2 // n_lp),
    )
    factor = 1 / n_lp / len(spg_reps.unique_rotation_indices)
    for i, _ in enumerate(spg_reps.unique_rotation_indices):
        mat = spg_reps.get_sigma2_rep(i)
        mat = mat @ C
        mat = C.T @ mat
        coset_reps_sum += kron(mat, spg_reps.r2_reps[i] * factor)
    return coset_reps_sum


def get_indep_atoms_by_lat_trans(trans_perms: np.ndarray) -> np.ndarray:
    """Return independent atoms by lattice translation symmetry.

    Parameters
    ----------
    trans_perms : np.ndarray
        Atom indices after lattice translations.
        shape=(lattice_translations, supercell_atoms)

    Returns
    -------
    np.ndarray
        Independent atoms.
        shape=(n_indep_atoms_by_lattice_translation,), dtype=int

    """
    unique_atoms: list[int] = []
    assert np.array_equal(trans_perms[0, :], range(trans_perms.shape[1]))
    for i, perms in enumerate(trans_perms.T):
        is_found = False
        for j in unique_atoms:
            if j in perms:
                is_found = True
                break
        if not is_found:
            unique_atoms.append(i)
    return np.array(unique_atoms, dtype=int)


def get_lat_trans_compr_matrix(decompr_idx: np.ndarray, N: int, n_lp: int) -> coo_array:
    """Return compression matrix by lattice translation symmetry.

    `decompr_idx` is obtained by `get_lat_trans_decompr_indices`.

    Matrix shape is (NN33, n_a*N33), where n_a is the number of independent
    atoms by lattice translation symmetry.

    Data order is (N, N, 3, 3, n_a, N, 3, 3) if it is in dense array.

    """
    NN9 = N**2 * 9
    compression_mat = coo_array(
        (
            np.full(NN9, 1 / np.sqrt(n_lp), dtype="double"),
            (np.arange(NN9, dtype=int), decompr_idx),
        ),
        shape=(NN9, NN9 // n_lp),
        dtype="double",
    )
    return compression_mat


def get_lat_trans_compr_indices(trans_perms: np.ndarray) -> np.ndarray:
    """Return indices to compress matrix by lat-trans-sym.

    Usage
    -----
    vec[indices] of shape (N**2*9,) vec gives an array of shape=(n_a*N*9, n_lp).
    1/sqrt(n_lp) must be multiplied manually after compression to mimic
    get_lat_trans_compr_matrix.

    Parameters
    ----------
    trans_perms : ndarray
        Permutation of atomic indices by lattice translational symmetry.
        dtype='intc'. shape=(n_l, N), where n_l and N are the numbers of lattce
        points and atoms in supercell.

    Returns
    -------
    indices : ndarray
        shape=(n_a*N9, n_lp), dtype='int_'.

    """
    indep_atoms = get_indep_atoms_by_lat_trans(trans_perms)
    n_a = len(indep_atoms)
    N = trans_perms.shape[1]
    n_lp = N // n_a
    size_row = (N * 3) ** 2

    n = 0
    indices = np.zeros((n_a * N * 9, n_lp), dtype="int_")
    for i_patom in indep_atoms:
        for j in range(N):
            for ab in range(9):
                indices[n, :] = (
                    trans_perms[:, i_patom] * 9 * N + trans_perms[:, j] * 9 + ab
                )
                n += 1
    assert n * n_lp == size_row
    return indices


def get_lat_trans_decompr_indices(trans_perms: np.ndarray) -> np.ndarray:
    """Return indices to de-compress compressed matrix by lat-trans-sym.

    Usage
    -----
    vec[indices] of shape (n_a*N*9,) gives an array of shape=(N**2*9,).
    1/sqrt(n_lp) must be multiplied manually after decompression to mimic
    get_lat_trans_compr_matrix.

    Parameters
    ----------
    trans_perms : ndarray
        Permutation of atomic indices by lattice translational symmetry.
        dtype='intc'.
        shape=(n_l, N), where n_l and N are the numbers of lattce points and
        atoms in supercell.

    Returns
    -------
    indices : ndarray
        Indices of n_a * N9 elements.
        shape=(N^2*9,), dtype='int_'.

    """
    indep_atoms = get_indep_atoms_by_lat_trans(trans_perms)
    n_a = len(indep_atoms)
    N = trans_perms.shape[1]
    n_lp = N // n_a
    size_row = (N * 3) ** 2

    n = 0
    indices = np.zeros(size_row, dtype="int_")
    for i_patom in indep_atoms:
        index_shift_i = trans_perms[:, i_patom] * N * 9
        for j in range(N):
            index_shift = index_shift_i + trans_perms[:, j] * 9
            for ab in range(9):
                indices[index_shift + ab] = n
                n += 1
    assert n * n_lp == size_row
    return indices


def get_perm_compr_matrix(natom: int) -> coo_array:
    """Return compression matrix by permutation symmetry.

    Parameters
    ----------
    natom : int
        Number of atoms in supercell.

    Matrix shape is (NN33,(N*3)(N*3+1)/2).
    Non-zero only ijab and jiba column elements for ijab rows.
    Rows upper right NN33 matrix elements are selected for rows.

    For the computational performance, get_perm_compr_matrix is implemented in a
    tricky way effectively using numpy features, and so it is not easy to read.
    What is expected may be found reading _get_perm_compr_matrix_reference.

    """
    N = natom
    A = np.transpose(
        np.arange(N**2 * 9).reshape(N, N, 3, 3), axes=(0, 2, 1, 3)
    ).reshape(N * 3, N * 3)
    ut = np.triu_indices_from(A, k=1)
    diag = np.diagonal(A)
    row = np.hstack((np.stack((A[ut], A.T[ut]), axis=1).ravel(), diag))
    col = np.hstack(
        (
            np.repeat(np.arange(len(ut[0]), dtype=int), 2),
            np.arange(len(ut[0]), len(ut[0]) + len(diag), dtype=int),
        )
    )
    data = np.hstack((np.full(len(ut[0]) * 2, np.sqrt(2) / 2), np.full(len(diag), 1)))
    return coo_array(
        (data, (row, col)),
        shape=(N**2 * 9, (N * 3 * (N * 3 + 1)) // 2),
        dtype="double",
    )


def get_atomic_lat_trans_decompr_indices(trans_perms: np.ndarray) -> np.ndarray:
    """Return indices to de-compress compressed matrix by atom-lat-trans-sym.

    This is atomic permutation only version of get_lat_trans_decompr_indices.

    Usage
    -----
    vec[indices] of shape (n_a*N,) gives an array of shape=(N**2,).
    1/sqrt(n_lp) must be multiplied manually after decompression.

    Parameters
    ----------
    trans_perms : ndarray
        Permutation of atomic indices by lattice translational symmetry.
        dtype='intc'.
        shape=(n_l, N), where n_l and N are the numbers of lattce points and
        atoms in supercell.

    Returns
    -------
    indices : ndarray
        Indices of n_a * N elements.
        shape=(N^2*,), dtype='int_'.

    """
    indep_atoms = get_indep_atoms_by_lat_trans(trans_perms)
    n_lp, N = trans_perms.shape
    size_row = N**2

    n = 0
    indices = np.zeros(size_row, dtype="int_")
    for i_patom in indep_atoms:
        index_shift_i = trans_perms[:, i_patom] * N
        for j in range(N):
            index_shift = index_shift_i + trans_perms[:, j]
            indices[index_shift] = n
            n += 1
    assert n * n_lp == size_row
    return indices


def _get_perm_compr_matrix_reference(natom: int) -> coo_array:
    """Return compression matrix by permutation symmetry.

    This is a reference implementation of get_perm_compr_matrix. The order of
    columns is difference from get_perm_compr_matrix, but it is OK if C.T@C
    is the same.

    Matrix shape is (NN33,(N*3)(N*3+1)/2). Non-zero only ijab and jiba column
    elements for ijab rows. Rows upper right NN33 matrix elements are selected
    for rows.

    """

    def to_serial(i: int, a: int, j: int, b: int, natom: int) -> int:
        """Return NN33-1D index."""
        return (i * 9 * natom) + (j * 9) + (a * 3) + b

    col, row, data = [], [], []
    val = np.sqrt(2) / 2
    size_row = natom**2 * 9

    n = 0
    for ia, jb in itertools.combinations_with_replacement(range(natom * 3), 2):
        i_i = ia // 3
        i_a = ia % 3
        i_j = jb // 3
        i_b = jb % 3
        col.append(n)
        row.append(to_serial(i_i, i_a, i_j, i_b, natom))
        if i_i == i_j and i_a == i_b:
            data.append(1)
        else:
            data.append(val)
            col.append(n)
            row.append(to_serial(i_j, i_b, i_i, i_a, natom))
            data.append(val)
        n += 1
    if (natom * 3) % 2 == 1:
        assert (natom * 3) * ((natom * 3 + 1) // 2) == n, f"{natom}, {n}"
    else:
        assert ((natom * 3) // 2) * (natom * 3 + 1) == n, f"{natom}, {n}"
    return coo_array((data, (row, col)), shape=(size_row, n), dtype="double")
