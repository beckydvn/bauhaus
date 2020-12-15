import weakref
# add try import
import nnf
from nnf import Var, And, NNF
from functools import wraps
from collections import defaultdict
import warnings
from constraint_builder import _ConstraintBuilder as cbuilder
from utils import flatten


class Encoding:
    """
    Creates an Encoding object. This will store propositions
    and constraints that you can compile into a theory.

    Attributes:

        propositions : defaultdict(weakref.WeakValueDictionary)
            Stores decorated classes/functions pointing to
            their associated instances.These are later used
            to build the theory's constraints.

        constraints : set
            A set of unique _ConstraintBuilder objects
            that hold relevant information to build an NNF
            constraint.
            They are added to the Encoding object whenever the
            constraint decorator is used or when it is called
            as a function.
        debug_constraints : dictionary
            Maps ConstraintBuilder objects to their compiled
            constraints for debugging purposes.

    """

    def __init__(self):
        self.propositions = defaultdict(weakref.WeakValueDictionary)
        self.constraints = set()
        self.debug_constraints = dict()

    def __repr__(self) -> str:
        return (f"Encoding: \n"
                f"  propositions::{self.propositions.keys()} \n"
                f"  constraints::{self.constraints}")
    
    def clear_debug(self):
        """Clear debug dictionary"""
        self.debug_constraints = dict()

    def compile(self, CNF=True) -> 'NNF':
        """ Convert constraints into a theory in
        conjunctive normal form, or if specified,
        the simpler negation-normal form.
        
        Arguments:
            CNF : bool
                Default is True. Converts a theory to CNF.

        """
        if not self.constraints:
            raise ValueError(f"Constraints in {self} are empty."
                             " This can happen if no objects from"
                             " decorated classes are instantiated,"
                             " if no classes/methods are decorated"
                             " with @constraint or no function"
                             " calls of the form constraint.add_method")
        if not self.propositions.values():
            raise ValueError(f"Constraints in {self} are empty."
                             " This can happen if no objects from"
                             " decorated classes are instantiated.")

        theory = []
        self.clear_debug()

        for constraint in self.constraints:
            clause = constraint.build(self.propositions)
            if CNF:
                clause = clause.to_CNF()
            if clause:
                theory.append(clause)
                try:
                    self.debug_constraints[constraint] = clause
                except Exception as e:
                    raise(e)
            else:
                warnings.warn(f"The {constraint} was not built and"
                            "will not be added to the theory.")
        return And(theory)

    def introspect(self):
        """Observing the origin of a theory from each
        propositional object to the final constraint.
        The mapping is structured like so,

        Encoding.debug_constraints : dictionary

            key: ConstraintBuilder object
            value: Clause built in Encoding.compile()
        
        Each ConstraintBuilder object has the attribute
        instance_constraints : defaultdict with,

            key: Object (from annotated class or method)
            value: List of constraint clauses created per object
        
        This allows you to view the constraints created
        for annotated classes or methods and the per-instance
        object constraints, along with the final (succinct)
        constraint.
        """
        if not self.debug_constraints:
            warnings.warn("Your theory has not been compiled yet,"
                          "so we cannot provide a representation of it." 
                          "Try running compile() on your encoding.")
            return self.debug_constraints

        for constraint, clause in self.debug_constraints.items():
            print(f"{constraint}: \n")
            if constraint.instance_constraints:
                for instance, values in constraint.instance_constraints.items():
                        print(f"{instance} =>")
                        for v in values:
                            print(f"{v}")
                        print("\n")
            print(f"Final {constraint._constraint.__name__}: {clause} \n")


def proposition(encoding: Encoding):
    """Create a propositional variable from the decorated
    class or function.
    
    Adds propositional variable to Encoding.

    Return original object instance.

    Examples:

        Each instance of class A is added to propositions
        in the given Encoding object.

        e = Encoding()
        @proposition(e)
        class A:
            pass
        >> e.propositions = {'A': {id: object}}

    Arguments:
        encoding : Encoding object.

    Returns:
        The decorated function.

    """
    def wrapper(cls):
        @wraps(cls)
        def wrapped(*args, **kwargs):
            ret = cls(*args, **kwargs)
            ret._var = Var(ret)
            class_name = ret.__class__.__qualname__
            encoding.propositions[class_name][id(ret)] = ret
            return ret
        return wrapped
    return wrapper


class constraint:
    """Creates constraints on the fly when
    used as a decorator or as a function invocation.

    The constraint class directs all function
    invokations of constraint methods to the
    classmethod constraint_by_function. 
    
    @constraint.method calls are directed
    to classmethod _decorate.

    In both cases, a ConstraintBuilder object
    is created to store the given information.

    Supports the following constraints:
        - At least one
        - At most one
        - Exactly one
        - At most K
        - Implies all

    Examples:
        Decorator for class or instance method:

            @constraint.method(e)
            @proposition
            class A:

                @constraint.method(e)
                def do_something(self):
                    pass

        Constraint creation by function call:
            constraint.add_method(e, *args)


    """
    @classmethod
    def constraint_by_function(cls, 
                               encoding: Encoding,
                               constraint_type,
                               args=None,
                               k=None,
                               left=None,
                               right=None):
        
        """
        Create _ConstraintBuilder objects from constraint.add_method
        function calls
        Arguments:
            encoding : Encoding object
            constraint_type : function
                Reference to the function for building an SAT encoding
                constraint in _ConstraintBuilder
            args : tuple
                Tuple of user-given arguments.
            k : int
                Used for constraint "At most K".
            left : tuple
                Used for constraint "implies all".
                User-given arguments for the left implication.
            right : tuple
                Used for constraint "implies all".
                User-given arguments for the right implication.
        Returns:
                Returns None
        """

        if constraint_type is cbuilder.implies_all:
            constraint = cbuilder(constraint_type, left=left, right=right)
            encoding.constraints.add(constraint)
            return
        elif args:
            args = tuple(flatten(args))
            constraint = cbuilder(constraint_type, args=args, k=k)
            encoding.constraints.add(constraint)
            return
        else:
            raise ValueError("Some or more of your provided"
                             f" arguments for the {constraint_type.__name__}"
                             " constraint were empty or invalid. Your" 
                             " provided arguments were: \n"
                            f" args: {args}, "
                            f" left: {left}, right: {right}")

    @classmethod
    def _decorate(cls,
                  encoding: Encoding,
                  constraint_type,
                  k=None,
                  left=None,
                  right=None):
        """
        Create _ConstraintBuilder objects from constraint.method
        function calls
        Arguments:
            constraint : function
                Reference to the function for building an SAT encoding
                constraint in _ConstraintBuilder
            func : function
                Decorated class or bound method. Default = None.
            k : int
                Used for constraint "At most K".
            left : tuple
                Used for constraint "implies all".
                User-given arguments for the left implication.
            right : tuple
                Used for constraint "implies all".
                User-given arguments for the right implication.
        Returns:
            Wrapper: Returns the function it decorated
        """
        def wrapper(func):
            constraint = cbuilder(constraint_type,
                                  func=func,
                                  k=k,
                                  left=left,
                                  right=right)
            encoding.constraints.add(constraint)

            @wraps(func)
            def wrapped(*args, **kwargs):
                ret = func(*args, **kwargs)
                return ret
            return wrapped
        return wrapper

    def at_least_one(encoding: Encoding):
        """At least one of the propositional variables are True. """
        return constraint._decorate(encoding, cbuilder.at_least_one)

    def at_most_one(encoding: Encoding):
        """At most one of the propositional variables are True. """
        return constraint._decorate(encoding, cbuilder.at_most_one)

    def exactly_one(encoding: Encoding):
        """ Exactly one of the propositional variables are True. """
        return constraint._decorate(encoding, cbuilder.exactly_one)

    def at_most_k(encoding: Encoding, k: int):
        """At most K of the propositional variables are True. """
        if not isinstance(k, int):
            raise TypeError(f"The provided k={k} is not an integer.")
        if k < 1:
            raise ValueError(f"The provided k={k} is less than 1.")
        if k == 1:
            warnings.warn(f"Warning: The provided k={k} will"
                           " result in an 'at most one' constraint,"
                           " but we'll proceed anyway.")
        return constraint._decorate(encoding,
                                    cbuilder.at_most_k,
                                    k=k)

    def implies_all(encoding: Encoding, left=None, right=None):
        """Left proposition(s) implies right proposition(s) """
        left = tuple(flatten([left])) if left else None
        right = tuple(flatten([right])) if right else None
        return constraint._decorate(encoding,
                                    cbuilder.implies_all,
                                    left=left, right=right)
    
    # Creating constraints from function invokations
    
    def add_at_least_one(encoding: Encoding, *args):
        """At least one of the propositional variables are True. """
        return constraint.constraint_by_function(encoding,
                                                 cbuilder.at_least_one,
                                                 args=args)

    def add_at_most_one(encoding: Encoding, *args):
        """At most one of the propositional variables are True. """
        return constraint.constraint_by_function(encoding,
                                                 cbuilder.at_most_one,
                                                 args=args)

    def add_exactly_one(encoding: Encoding, *args):
        """ Exactly one of the propositional variables are True. """
        return constraint.constraint_by_function(encoding,
                                                 cbuilder.exactly_one,
                                                 args=args)

    def add_at_most_k(encoding: Encoding, k: int, *args):
        """At most K of the propositional variables are True. """
        if not isinstance(k, int):
            raise TypeError(f"The provided k={k} is not an integer.")
        if k < 1:
            raise ValueError(f"The provided k={k} is less than 1.")
        if k == 1:
            warnings.warn(f"Warning: The provided k={k} will"
                           " result in an 'at most one' constraint,"
                           " but we'll proceed anyway.")
        return constraint.constraint_by_function(encoding,
                                                 cbuilder.at_most_k,
                                                 args=args, k=k)

    def add_implies_all(encoding: Encoding, left, right):
        """Left proposition(s) implies right proposition(s) """
        if not (left and right):
            raise ValueError(f"You are trying to create an implies all"
                              " constraint without providing either the left"
                              " or right sides of the implication. \n"
                             f" Your left: {left} and right: {right}")
        left = tuple(flatten([left]))
        right = tuple(flatten([right]))
        return constraint.constraint_by_function(encoding,
                                                 cbuilder.implies_all,
                                                 left=left, right=right)

e = Encoding()

@constraint.implies_all(e, right=['hello'])
@constraint.at_most_k(e, 2)
@proposition(e)
class A(object):

    def __init__(self, val):
        self.val = val

    def __repr__(self):
        return f"A.{self.val}"

    # Each instance of A implies the result of the method
    @constraint.implies_all(e)
    def foo(self):
        return self.val

# At most one of the inputs is true. 
constraint.add_at_most_one(e, A, A.foo, Var('B'))
obj = [A(val) for val in range(1,4)]
theory = e.compile()
print(theory)
e.introspect()