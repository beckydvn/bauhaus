from nnf import NNF, And, Or, Var
from itertools import chain
from utils import ismethod, unpack_variables, flatten
from inspect import isclass


class _ConstraintBuilder:
    """
    Stores information necessary to build encoding constraint
    from constraint.method calls. Instances are stored in the
    list attribute 'constraints' in Encoding objects that are
    provided to the constraint.method

    Supports following SAT constraints:
    - at least one
    - at most one
    - at most k
    - implies all
    - exactly one

    """

    def __init__(self, constraint, args, func=None, cls=None, k=None):
        self._constraint = constraint
        self._vars = tuple(flatten(args))
        self._func = func
        self._k = k

    def __hash__(self):
        return hash((self._constraint, self._vars, self._func, self._k))

    def __eq__(self, other):
        if isinstance(other, _ConstraintBuilder):
            return self.__hash__() == other.__hash__()
        raise NotImplemented

    def __str__(self):
        return f'constraint:{self._constraint}, variables:{self._vars}, function:{self._func}'

    def build(self, propositions) -> NNF:
        """ 
        Validates and unpacks variables from an _ConstraintBuilder object
        and its associated Encoding. Returns the SAT constraint.

        :param propositions: defaultdict(weakref.WeakValueDictionary)
        :param self: ConstraintBuilder
        """
        inputs = self.get_inputs(propositions)
        return self._constraint(inputs)


    def get_inputs(self, propositions) -> list:
        """ Returns a list of inputs to be used for building the constraint.
        
        If the ConstraintBuilder was created for a decorated class or method,
        then we check if the decorated class is in the Encoding.propositions
        and return its instances.
        If the ConstraintBuilder does not have '_func', then it was invoked as 
        a function call. We gather its arguments (self._vars) and return.

        :param propositions: defaultdict(weakref.WeakValueDictionary)
        :param self: ConstraintBuilder
        :type ConstraintBuilder._vars: tuple
        """

        inputs = []
        
        # Annotated class or its instance method
        if self._func:

            if self._vars:
                additional_vars = unpack_variables(self._vars, propositions)
                inputs.append(additional_vars)

            if self._func.__qualname__ in propositions:
                self._cls = self._func.__qualname__

                for instance_id in propositions[self._cls]:
                    obj = propositions[self._cls][instance_id]
                    inputs.append(obj._var)
                return inputs

            elif ismethod(self._func):
                
                # hacky but no proper way to do it during object creation as the method
                # is added before classes are defined or after since inspect cannot get us the class
                self._cls = self._func.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0]

                for instance_id in propositions[self._cls]:
                    obj = propositions[self._cls][instance_id]
                    # TODO: https://github.com/QuMuLab/bauhaus/issues/21
                    inputs.append({obj: [*self._func(obj)]})
                return inputs

            else:
                # TODO: specify exception
                raise Exception(f"{self._func} should be decorated.")

        else:
            # Inputs from method call
            inputs = list(unpack_variables(self._vars, propositions))
            
        return inputs


    """ Constraint methods 
    
    #TODO: a biggie, but can leave till later

    """

    def at_least_one(inputs: list) -> NNF:
        """ Disjunction across all variables """
        return Or(inputs)

    def at_most_one(inputs: list) -> NNF:
        """ And(Or(~a, ~b)) for all a,b in input 
        use functools.product(input)
        """
        pass

    def exactly_one(inputs: list) -> NNF:
        """ 
        Exactly one variable can be true of the input 
        And(at_most_one, at_least_one) 
        """
        pass

    def at_most_k(inputs: list, k=1) -> NNF:
        """ At most k variables can be true """
        pass

    def implies_all(inputs: list) -> NNF:
        """ And(Or(~left, right)) """
        pass
