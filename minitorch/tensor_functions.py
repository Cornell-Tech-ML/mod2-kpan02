# pyright: reportOptionalMemberAccess=false
"""Implementation of the autodifferentiation Functions for Tensor."""

from __future__ import annotations

import random
from typing import TYPE_CHECKING

import numpy as np

import minitorch

from . import operators
from .autodiff import Context
from .tensor_ops import SimpleBackend, TensorBackend

if TYPE_CHECKING:
    from typing import Any, List, Optional, Tuple

    from .tensor import Tensor
    from .tensor_data import UserIndex, UserShape


def wrap_tuple(x: Any) -> tuple:  # type: ignore
    """Turn a possible value into a tuple"""
    if isinstance(x, tuple):
        return x
    return (x,)


# Constructors
class Function:
    @classmethod
    def _backward(cls, ctx: Context, grad_out: Tensor) -> Tuple[Tensor, ...]:
        return wrap_tuple(cls.backward(ctx, grad_out))  # type: ignore

    @classmethod
    def _forward(cls, ctx: Context, *inps: Tensor) -> Tensor:
        return cls.forward(ctx, *inps)  # type: ignore

    @classmethod
    def apply(cls, *vals: Tensor) -> Tensor:
        """Call the forward function and track history"""
        raw_vals = []
        need_grad = False
        for v in vals:
            if v.requires_grad():
                need_grad = True
            raw_vals.append(v.detach())

        # Create the context.
        ctx = Context(not need_grad)

        # Call forward with the variables.
        c = cls._forward(ctx, *raw_vals)
        # assert isinstance(c, Tensor), "Expected return type Tensor got %s" % (
        #     type(c)
        # )

        # Create a new variable from the result with a new history.
        back = None
        if need_grad:
            back = minitorch.History(cls, ctx, vals)
        return minitorch.Tensor(c._tensor, back, backend=c.backend)


class Neg(Function):
    @staticmethod
    def forward(ctx: Context, t1: Tensor) -> Tensor:
        """Negate the input tensor."""
        assert t1.f is not None
        return t1.f.neg_map(t1)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Compute gradient for negation operation."""
        return grad_output.f.neg_map(grad_output)


class Inv(Function):
    @staticmethod
    def forward(ctx: Context, t1: Tensor) -> Tensor:
        """Compute the element-wise inverse of the input tensor."""
        ctx.save_for_backward(t1)
        return t1.f.inv_map(t1)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Compute gradient for inverse operation."""
        (t1,) = ctx.saved_values
        return grad_output.f.inv_back_zip(t1, grad_output)


class Add(Function):
    @staticmethod
    def forward(ctx: Context, t1: Tensor, t2: Tensor) -> Tensor:
        """Add two tensors element-wise."""
        return t1.f.add_zip(t1, t2)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Compute gradient for addition operation."""
        return grad_output, grad_output


class All(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, dim: Tensor) -> Tensor:
        """Return 1 if all are true"""
        if dim is not None:
            return a.f.mul_reduce(a, int(dim.item()))
        else:
            return a.f.mul_reduce(a.contiguous().view(int(operators.prod(a.shape))), 0)


# TODO: Implement for Task 2.3.
class Mul(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, b: Tensor) -> Tensor:
        """Forward pass for element-wise multiplication of two tensors.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The first input tensor.
            b (Tensor): The second input tensor.

        Returns:
        -------
            Tensor: The result of element-wise multiplication of a and b.

        """
        ctx.save_for_backward(a, b)
        return a.f.mul_zip(a, b)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Backward pass for element-wise multiplication.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tuple[Tensor, Tensor]: The gradients with respect to inputs a and b.

        """
        a, b = ctx.saved_values
        grad_a = grad_output.f.mul_zip(grad_output, b)
        grad_b = grad_output.f.mul_zip(grad_output, a)
        return grad_a, grad_b


class Sigmoid(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor) -> Tensor:
        """Forward pass for the sigmoid activation function.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The input tensor.

        Returns:
        -------
            Tensor: The result of applying the sigmoid function to the input.

        """
        out = a.f.sigmoid_map(a)
        ctx.save_for_backward(out)
        return out

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Backward pass for the sigmoid activation function.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tensor: The gradient with respect to the input.

        """
        (out,) = ctx.saved_values
        one = minitorch.tensor([1.0])
        return grad_output * out * (one - out)


class ReLU(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor) -> Tensor:
        """Forward pass for the ReLU activation function.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The input tensor.

        Returns:
        -------
            Tensor: The result of applying the ReLU function to the input.

        """
        ctx.save_for_backward(a)
        return a.f.relu_map(a)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Backward pass for the ReLU activation function.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tensor: The gradient with respect to the input.

        """
        (a,) = ctx.saved_values
        return grad_output * a.f.relu_back_zip(a, grad_output)


class Log(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor) -> Tensor:
        """Forward pass for the natural logarithm function.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The input tensor.

        Returns:
        -------
            Tensor: The result of applying the natural logarithm to the input.

        """
        ctx.save_for_backward(a)
        return a.f.log_map(a)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Backward pass for the natural logarithm function.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tensor: The gradient with respect to the input.

        """
        (a,) = ctx.saved_values
        return grad_output / a


class Exp(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor) -> Tensor:
        """Forward pass for the exponential function.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The input tensor.

        Returns:
        -------
            Tensor: The result of applying the exponential function to the input.

        """
        out = a.f.exp_map(a)
        ctx.save_for_backward(out)
        return out

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Backward pass for the exponential function.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tensor: The gradient with respect to the input.

        """
        (out,) = ctx.saved_values
        return grad_output * out


class Sum(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, dim: Optional[Tensor] | None) -> Tensor:
        """Forward pass for the sum reduction operation.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The input tensor.
            dim (Optional[Tensor] | None): The dimension(s) to sum over.

        Returns:
        -------
            Tensor: The result of summing the input tensor over the specified dimension(s).

        """
        ctx.save_for_backward(a, dim)
        if dim is None:
            return a
        dims_to_sum = (
            [int(d) for d in dim._tensor._storage]
            if dim._tensor.size > 1
            else [int(dim._tensor._storage[0])]
        )
        result = a
        for d in dims_to_sum:
            result = result.f.add_reduce(result, d)
        return (
            result if result._tensor.size > 1 else tensor([result._tensor._storage[0]])
        )

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Backward pass for the sum reduction operation.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tuple[Tensor, Tensor]: The gradients with respect to the input and the dimension.

        """
        (a, dim) = ctx.saved_values
        if dim is None:
            return a.expand(grad_output)  # TODO
        else:
            return a.expand(grad_output), zeros(dim.shape)


class LT(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, b: Tensor) -> Tensor:
        """Forward pass for the less than comparison operation.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The first input tensor.
            b (Tensor): The second input tensor.

        Returns:
        -------
            Tensor: A boolean tensor where True indicates a < b element-wise.

        """
        return a.f.lt_zip(a, b)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Backward pass for the less than comparison operation.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tuple[Tensor, Tensor]: Zero gradients for both inputs (comparison is not differentiable).

        """
        return zeros(grad_output.shape), zeros(grad_output.shape)


class EQ(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, b: Tensor) -> Tensor:
        """Forward pass for the equality comparison operation.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The first input tensor.
            b (Tensor): The second input tensor.

        Returns:
        -------
            Tensor: A boolean tensor where True indicates a == b element-wise.

        """
        return a.f.eq_zip(a, b)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Backward pass for the equality comparison operation.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tuple[Tensor, Tensor]: Zero gradients for both inputs (comparison is not differentiable).

        """
        return zeros(grad_output.shape), zeros(grad_output.shape)


class IsClose(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, b: Tensor) -> Tensor:
        """Forward pass for the is_close comparison operation.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The first input tensor.
            b (Tensor): The second input tensor.

        Returns:
        -------
            Tensor: A boolean tensor where True indicates a is close to b element-wise.

        """
        return a.f.is_close_zip(a, b)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Backward pass for the is_close comparison operation.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tuple[Tensor, Tensor]: Zero gradients for both inputs (comparison is not differentiable).

        """
        return zeros(grad_output.shape), zeros(grad_output.shape)


class Permute(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, order: Tensor) -> Tensor:
        """Forward pass for the permute operation.

        Args:
        ----
            ctx (Context): The context for saving values for backward pass.
            a (Tensor): The input tensor to be permuted.
            order (Tensor): The new order of dimensions.

        Returns:
        -------
            Tensor: The permuted tensor.

        """
        orders = order.to_numpy().astype(int).tolist()
        ctx.save_for_backward(orders)
        return a._new(a._tensor.permute(*orders))

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, float]:
        """Backward pass for the permute operation.

        Args:
        ----
            ctx (Context): The context containing saved tensors from the forward pass.
            grad_output (Tensor): The gradient of the loss with respect to the output.

        Returns:
        -------
            Tuple[Tensor, float]: The gradient with respect to the input and a zero gradient for the order.

        """
        (orders,) = ctx.saved_values
        reverse = [0] * len(orders)
        for i in range(len(orders)):
            reverse[int(orders[i])] = i
        return grad_output._new(grad_output._tensor.permute(*reverse)), 0.0


class View(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor, shape: Tensor) -> Tensor:
        """Reshape a tensor to the specified shape."""
        ctx.save_for_backward(a.shape)
        assert a._tensor.is_contiguous(), "Must be contiguous to view"
        shape2 = [int(shape[i]) for i in range(shape.size)]
        return minitorch.Tensor.make(
            a._tensor._storage, tuple(shape2), backend=a.backend
        )

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, float]:
        """Matrix Multiply backward (module 3)"""
        (original,) = ctx.saved_values
        return (
            minitorch.Tensor.make(
                grad_output._tensor._storage, original, backend=grad_output.backend
            ),
            0.0,
        )


class Copy(Function):
    @staticmethod
    def forward(ctx: Context, a: Tensor) -> Tensor:
        """Id function makes contiguous"""
        return a.f.id_map(a)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tensor:
        """Undo"""
        return grad_output


class MatMul(Function):
    @staticmethod
    def forward(ctx: Context, t1: Tensor, t2: Tensor) -> Tensor:
        """Matrix Multiply Forward (module 3)"""
        ctx.save_for_backward(t1, t2)
        return t1.f.matrix_multiply(t1, t2)

    @staticmethod
    def backward(ctx: Context, grad_output: Tensor) -> Tuple[Tensor, Tensor]:
        """Matrix Multiply backward (module 3)"""
        t1, t2 = ctx.saved_values

        def transpose(a: Tensor) -> Tensor:
            order = list(range(a.dims))
            order[-2], order[-1] = order[-1], order[-2]
            return a._new(a._tensor.permute(*order))

        return (
            grad_output.f.matrix_multiply(grad_output, transpose(t2)),
            grad_output.f.matrix_multiply(transpose(t1), grad_output),
        )


# Helpers for Constructing tensors
def zeros(shape: UserShape, backend: TensorBackend = SimpleBackend) -> Tensor:
    """Produce a zero tensor of size `shape`.

    Args:
    ----
        shape : shape of tensor
        backend : tensor backend

    Returns:
    -------
        new tensor

    """
    return minitorch.Tensor.make(
        [0.0] * int(operators.prod(shape)), shape, backend=backend
    )


def rand(
    shape: UserShape,
    backend: TensorBackend = SimpleBackend,
    requires_grad: bool = False,
) -> Tensor:
    """Produce a random tensor of size `shape`.

    Args:
    ----
        shape : shape of tensor
        backend : tensor backend
        requires_grad : turn on autodifferentiation

    Returns:
    -------
        :class:`Tensor` : new tensor

    """
    vals = [random.random() for _ in range(int(operators.prod(shape)))]
    tensor = minitorch.Tensor.make(vals, shape, backend=backend)
    tensor.requires_grad_(requires_grad)
    return tensor


def _tensor(
    ls: Any,
    shape: UserShape,
    backend: TensorBackend = SimpleBackend,
    requires_grad: bool = False,
) -> Tensor:
    """Produce a tensor with data ls and shape `shape`.

    Args:
    ----
        ls: data for tensor
        shape: shape of tensor
        backend: tensor backend
        requires_grad: turn on autodifferentiation

    Returns:
    -------
        new tensor

    """
    tensor = minitorch.Tensor.make(ls, shape, backend=backend)
    tensor.requires_grad_(requires_grad)
    return tensor


def tensor(
    ls: Any, backend: TensorBackend = SimpleBackend, requires_grad: bool = False
) -> Tensor:
    """Produce a tensor with data and shape from ls

    Args:
    ----
        ls: data for tensor
        backend : tensor backend
        requires_grad : turn on autodifferentiation

    Returns:
    -------
        :class:`Tensor` : new tensor

    """

    def shape(ls: Any) -> List[int]:
        if isinstance(ls, (list, tuple)):
            return [len(ls)] + shape(ls[0])
        else:
            return []

    def flatten(ls: Any) -> List[float]:
        if isinstance(ls, (list, tuple)):
            return [y for x in ls for y in flatten(x)]
        else:
            return [ls]

    cur = flatten(ls)
    shape2 = shape(ls)
    return _tensor(cur, tuple(shape2), backend=backend, requires_grad=requires_grad)


# Gradient check for tensors


def grad_central_difference(
    f: Any, *vals: Tensor, arg: int = 0, epsilon: float = 1e-6, ind: UserIndex
) -> float:
    """Compute gradient using central difference method."""
    x = vals[arg]
    up = zeros(x.shape)
    up[ind] = epsilon
    vals1 = [x if j != arg else x + up for j, x in enumerate(vals)]
    vals2 = [x if j != arg else x - up for j, x in enumerate(vals)]
    delta: Tensor = f(*vals1).sum() - f(*vals2).sum()

    return delta[0] / (2.0 * epsilon)


def grad_check(f: Any, *vals: Tensor) -> None:
    """Check whether autodiff matches central difference."""
    for x in vals:
        x.requires_grad_(True)
        x.zero_grad_()
    random.seed(10)
    out = f(*vals)
    out.sum().backward()
    err_msg = """

Gradient check error for function %s.

Input %s

Received derivative %f for argument %d and index %s,
but was expecting derivative %f from central difference.

"""

    for i, x in enumerate(vals):
        ind = x._tensor.sample()
        check = grad_central_difference(f, *vals, arg=i, ind=ind)
        assert x.grad is not None
        np.testing.assert_allclose(
            x.grad[ind],
            check,
            1e-2,
            1e-2,
            err_msg=err_msg % (f, vals, x.grad[ind], i, ind, check),
        )
