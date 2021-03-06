from coregister.transform import (
        Transform, TransformList, PolynomialModel, ChunkedModel)
import numpy as np
import pytest


@pytest.mark.parametrize('order', [1, 2, 3])
def test_polynomial_identity(order):
    t = Transform(name="PolynomialModel", order=order)
    src = np.random.randn(100, 3)
    assert np.allclose(t.tform(src), src)


@pytest.mark.parametrize('order', [1, 2, 3])
def test_polynomial_solution(order):
    shape = (100, 3)
    src = np.random.randn(*shape) * 1000
    t = Transform(name="PolynomialModel", order=1)
    t.parameters = np.array([
        [100, -234, 456],
        [1.01, 0.01, -0.01],
        [-0.002, 0.97, 0.05],
        [-0.03, 0.001, 1.02]])
    noise = np.random.randn(*shape)
    dst = t.tform(src) + noise

    tfit = Transform(name="PolynomialModel", order=order)
    tfit.estimate(src, dst)
    tdst = tfit.tform(src)

    residuals = tdst - dst
    rmag = np.linalg.norm(residuals, axis=1)
    assert np.all(rmag < np.linalg.norm(noise, axis=1).max() * 2)


@pytest.mark.parametrize('order', [1, 2, 3])
def test_poly_to_from_dict(order):
    t = Transform('PolynomialModel', order=order)
    t.parameters += np.random.randn(*t.parameters.shape) * 0.1
    jt = t.to_dict()

    t2 = Transform(json=jt)

    assert t2.order == t.order
    assert np.allclose(t2.parameters, t.parameters)

    tp = PolynomialModel(json=jt)
    assert tp.order == t.order
    assert np.allclose(tp.parameters, t.parameters)


@pytest.mark.parametrize('order', [0, 4])
def test_polynomial_order(order):
    with pytest.raises(ValueError):
        Transform(name="PolynomialModel", order=order)


@pytest.mark.parametrize('order', [1, 2, 3])
@pytest.mark.parametrize('axis', [0, 1, 2])
def test_chunked_identity(order, axis):
    t = Transform('ChunkedModel', order=order, axis=axis, nchunks=10)
    src = np.random.rand(10000, 3)
    t.estimate(src, src)
    dst = t.tform(src)
    assert np.allclose(src, dst)

    identity = Transform("PolynomialModel", order=order)
    for tf in t.transforms:
        if order == 3:
            assert np.allclose(
                    identity.parameters, tf.parameters, rtol=0, atol=1e-3)
        else:
            assert np.allclose(identity.parameters, tf.parameters)


def test_chunked_ranges():
    order = 1
    axis = 2
    t = Transform('ChunkedModel', order=order, axis=axis, nchunks=10)
    src = np.random.randn(1000, 3)
    t.estimate(src, src)

    t2 = Transform('ChunkedModel', order=order, axis=axis, ranges=t.ranges)
    assert t.nchunks == t2.nchunks
    assert np.allclose(t.ranges, t2.ranges)

    t2 = Transform('ChunkedModel', order=order, axis=axis, nchunks=t.nchunks)
    t2.set_ranges(ranges=t.ranges)
    assert t.nchunks == t2.nchunks
    assert np.allclose(t.ranges, t2.ranges)


def random_affine_parameters():
    p = np.random.randn(3) * 10
    p = np.vstack((p, np.eye(3)))
    p[1:4, :] += np.random.randn(3, 3) * 0.01
    return p


def test_chunked_values():
    order = 1
    axis = 2
    nchunks = 10
    src = np.random.rand(5000, 3)
    t1 = PolynomialModel(order=order, parameters=random_affine_parameters())
    t2 = PolynomialModel(order=order, parameters=random_affine_parameters())

    ranges = np.linspace(
            src[:, axis].min(),
            src[:, axis].max(),
            nchunks)[1:-1]

    inds_for_t2 = [3, 6, 7]

    dst = np.zeros_like(src)
    which = np.searchsorted(ranges, src[:, axis])
    for i in range(nchunks):
        inds = which == i
        tf = t1
        if i in inds_for_t2:
            tf = t2
        dst[inds, :] = tf.tform(src[inds, :])

    t = Transform('ChunkedModel', order=order, axis=axis, ranges=ranges)
    t.estimate(src, dst)

    tsrc = t.tform(src)
    res = np.linalg.norm(tsrc - dst, axis=1)
    assert res.mean() < np.linalg.norm(dst, axis=1).mean() * 0.001

    tc = ChunkedModel(order=order, axis=axis, ranges=ranges)
    tc.estimate(src, dst)

    tsrc = tc.tform(src)
    res = np.linalg.norm(tsrc - dst, axis=1)
    assert res.mean() < np.linalg.norm(dst, axis=1).mean() * 0.001

    # to and from dict
    jt = t.to_dict()
    td = Transform(json=jt)
    tsrc = td.tform(src)
    res = np.linalg.norm(tsrc - dst, axis=1)
    assert res.mean() < np.linalg.norm(dst, axis=1).mean() * 0.001


def test_spline_identity():
    t = Transform(name="SplineModel")
    src = np.random.randn(100, 3)
    t.set_control_pts_from_src(src)
    assert np.allclose(t.tform(src), src)


def test_spline_solution():
    t = Transform(name="SplineModel")
    src = np.random.randn(100, 3)
    t.estimate(src, src)
    assert np.allclose(t.tform(src), src)


def test_spline_complicated_solution():
    tp = Transform(name="PolynomialModel", order=2)
    tp.parameters[0, :] = np.random.randn(3)
    tp.parameters[1:4, :] += np.random.randn(3, 3) * 0.02
    tp.parameters[4:10, :] += np.random.randn(6, 3) * 0.0002

    src = np.random.randn(3000, 3)
    noise = np.random.randn(*src.shape) * 0.001
    dst = tp.tform(src) + noise

    ts = Transform(name="SplineModel", ncntrl=[10, 10, 10])
    ts.estimate(src, dst)
    res = ts.tform(src) - dst
    rmag = np.linalg.norm(res, axis=1)
    assert rmag.mean() < np.linalg.norm(noise, axis=1).mean() * 10

    # to from dict
    td = Transform(json=ts.to_dict())
    res = td.tform(src) - dst
    rmag = np.linalg.norm(res, axis=1)
    assert rmag.mean() < np.linalg.norm(noise, axis=1).mean() * 10

    # set via init
    tinit = Transform(
            name="SplineModel",
            parameters=td.parameters.tolist(),
            control_pts=td.control_pts.tolist())
    res = tinit.tform(src) - dst
    rmag = np.linalg.norm(res, axis=1)
    assert rmag.mean() < np.linalg.norm(noise, axis=1).mean() * 10

    # exact src points
    ts = Transform(name="SplineModel", src_is_cntrl=True)
    ts.estimate(src, dst)
    res = ts.tform(src) - dst
    rmag = np.linalg.norm(res, axis=1)
    assert rmag.mean() < 1e-3


def test_transform_list():
    tp = Transform(name="PolynomialModel", order=2)
    tp.parameters[0, :] = np.random.randn(3)
    tp.parameters[1:4, :] += np.random.randn(3, 3) * 0.02
    tp.parameters[4:10, :] += np.random.randn(6, 3) * 0.0002
    src = np.random.randn(3000, 3)
    noise = np.random.randn(*src.shape) * 0.001
    dst = tp.tform(src) + noise

    tflist_args = [
            {
                'name': "PolynomialModel",
                'order': 1
                },
            {
                'name': 'ChunkedModel',
                'order': 1,
                'axis': 2,
                'nchunks': 4
                },
            {
                'name': 'SplineModel',
                'ncntrl': [3, 3, 3]
                },
            {
                'name': 'SplineModel',
                'src_is_cntrl': True
                }
            ]
    tflist = TransformList(transforms=tflist_args)

    tflist.estimate(src, dst)
    tsrc = tflist.tform(src)
    rmag = np.linalg.norm(dst - tsrc, axis=1)
    assert rmag.mean() < 0.001

    # to from dict
    tflist2 = TransformList(json=tflist.to_dict())
    tsrc2 = tflist2.tform(src)
    rmag2 = np.linalg.norm(dst - tsrc2, axis=1)
    assert rmag2.mean() < 0.001
    assert np.allclose(tsrc, tsrc2)

    # as Transform
    tf = Transform(json=tflist.to_dict())
    tsrc3 = tf.tform(src)
    rmag3 = np.linalg.norm(dst - tsrc3, axis=1)
    assert rmag3.mean() < 0.001
    assert np.allclose(tsrc, tsrc3)
