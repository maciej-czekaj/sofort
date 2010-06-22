
WORD = 4 # machine word size

class Type:
    
    def __str__(self):
        return self.name
        
    def typeof(self,other):
        return isinstance(self,other.__class__) or isinstance(other,self.__class__) 

    def get_operation(self,operation):
        opname = 'op_'+operation
        return getattr(self,opname,None)

    def union(self,other):
        if isinstance(self,other.__class__):
            return other
        elif isinstance(other,self.__class__):
            return self
        else:
            return None
            
class ComplexType(Type):
    ''' 
    Complex type is represented as a structure and is larger than signle machine word.
    It is kept in the heap and it's pointer in kept on the stack. Registers are used to access the pointer.
    We assume that complex variable's address is stored in esi
    as opposed to basic type stored in eax. Thus indirect loads and stores do not affect
    direct ones as much. Moreover, it simplifies code generation since we have one default register 
    for indirect access.
    '''

    def store(self,emitter,stack_index):
        # No direct stores of complex types
        emitter.store_pointer(stack_index)        

    def load(self,emitter,stack_index):
        # Load pointer to structure
        emitter.load_pointer(stack_index)        

    def push(self,emitter):
        emitter.push_pointer()
        

class BasicType(Type):
    ''' 
    Basic type is representable by single machine word.
    It is kept on the stack or in the register as a word regardless of declared size.
    Real size counts when creating arrays.
    '''
    def store(self,emitter,stack_index):
        emitter.store_var_int(stack_index)

    def load(self,emitter,stack_index):
        emitter.load_var_int(stack_index)

    def push(self,emitter):
        emitter.push_acc()


class Array(ComplexType):
    ''' Array of homogeneous objects: <ptr> --> <hdr><n><el_1><el_2>....<el_n>
        It's contents is allocated dynamically.
    '''
    name = 'array'
    def __init__(self,subtype):
        self.subtype = subtype
        self.sizeof = WORD
        self.stack_size = 1
        
    def alloc(self,emitter,length):
        # Word for header, word for length, rest for contents
        emitter.call('malloc',2*WORD+length*subtype.sizeof)
        
# class ArrayConstant(ComplexType):
    # ''' C-like array initiated by literal, thus it's size
        # is known at compile time. 
        # struct array_const<T> { T*arr; }
    # '''
    # name = 'array'
    
    # def __init__(self,subtype,length):
        # self.length = length
        # self.sizeof = WORD
        # self.stack_size = 1

        
class String(ComplexType):
    ''' String is array of chars: struct string { char *arr; int len }
        This string type is mutable.
    '''  
    name = 'string'
    
    def __init__(self):
        self.sizeof = 2*WORD
        self.stack_size = 2

class StringConstant(ComplexType):
    ''' C-like string constant: struct string_const { char *arr; }
        It points to string literal stored in data segment.
    '''  
    
    def __init__(self,length):
        self.length = length
        self.sizeof = length
        self.stack_size = 1
    
    
class Char(BasicType):

    name = 'char'

    def __init__(self):
        self.sizeof = 1
        self.stack_size = 1
    
    def load_literal(self,emitter,literal):
        emitter.load_imm_int(ord(literal))
    
        
class Int(BasicType):

    name = 'int'

    def __init__(self):
        self.sizeof = WORD
        self.stack_size = 1
        
    def op_neg(self,emitter):
        emitter.neg_acc_int()
        
    def op_add(self,emitter):
        emitter.pop_add_int()

    def op_sub(self,emitter):
        emitter.pop_sub_int()

    def op_mul(self,emitter):
        emitter.pop_mul_int()
        
    def op_div(self,emitter):
        emitter.pop_div_int()
     
    def op_ge(self,emitter):
        emitter.pop_ge_int()
        
    def op_gt(self,emitter):
        emitter.pop_gt_int()

    def op_le(self,emitter):
        emitter.pop_le_int()
        
    def op_lt(self,emitter):
        emitter.pop_lt_int()

    def load_literal(self,emitter,literal):
        emitter.load_imm_int(literal)
    
# class IntConstant(Int):
    # name = 'IntConstant'
    # def __init__(self,literal):
        # Int.__init__(self)
        # self.literal = literal
    # def load(self,emitter):
        # emitter.load_imm_int(self.literal)
# class Unsupported:
    # pass
# IntConstant.store = Unsupported() # unsupported operation

class Char(BasicType):

    def __init__(self,literal=None):
        self.literal = literal
        self.sizeof = 1 # For now
        self.stack_size = 1
        
class Array(ComplexType):
    # struct array[T] { T *arr; int len }
    
    def __init__(self,element_type,literal=None):
        self.literal = literal
        self.element_type = element_type
        self.sizeof = 2*WORD
        self.stack_size = 2
