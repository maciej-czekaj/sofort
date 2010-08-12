
WORD = 4 # machine word size

def powerOf2(n):
    pow = 1
    for i in range(WORD*8):
        if n == pow:
            return i
        pow *= 2
    return None
    
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
        # Store new pointer
        emitter.store_var_pointer(stack_index)        

    def load(self,emitter,stack_index):
        # Load pointer to structure
        emitter.load_var_pointer(stack_index)        

    def push(self,emitter):
        emitter.push_pointer()
        
    def pop(self,emitter):
        emitter.pop_pointer()

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

# Abstract subclass for all array-like types
class Array(ComplexType):
    pass
        
class DynamicArray(Array):
    ''' Array of homogeneous objects: <ptr> --> <hdr><n><el_1><el_2>....<el_n>
        It's contents is allocated dynamically.
    '''
    name = 'array'
    def __init__(self,subtype):
        self.subtype = subtype
        self.sizeof = WORD
        self.stack_size = 1
        self.header_size = 2*WORD
        shift = powerOf2(subtype.sizeof)
        if shift == 1:
            self.offset_op = lambda e: None
        elif shift is None:
            self.offset_op = lambda e: e.mul_imm_int(subtype.sizeof)
        else:
            self.offset_op = lambda e: e.shl_imm_int(shift)
    
    def mul_offset(self,emitter):
        emitter.mul_imm_int(self.subtype.sizeof)
    
    def shl_offset(self,emitter):
        emitter.shl_imm_int(self.subtype.sizeof)
    
    def alloc(self,emitter,length):
        # Word for header, word for length, rest for contents
        emitter.push_imm_int(2*WORD+length*self.subtype.sizeof)
        emitter.call('malloc',1)
        emitter.move_pointer()
        self.length = length
        
    def store_at(self,emitter,index=0):
        self.subtype.store_at(emitter,index*self.subtype.sizeof+self.header_size)
        
    def load_at(self,emitter,index=0):
        self.subtype.load_at(emitter,index*self.subtype.sizeof+self.header_size)
        
    def add_offset(self,emitter):
        emitter.push_acc()
        emitter.push_acc()
        self.op_len(emitter)
        emitter.pop_cmp_int()
        label = emitter.new_label()
        emitter.jump_if_less(label)
        emitter.call('exception',0)
        emitter.label(label)
        emitter.pop_acc()
        self.offset_op(emitter) # acc *= sizeof(subtype)
        emitter.add_acc_to_pointer()
    
    def set_length(self,emitter,length):
        emitter.store_imm_int_at(1,length)
        
    def op_len(self,emitter):
        emitter.load_acc_int_at(1)
        
class String(DynamicArray):
    ''' String is array of chars. This string type is mutable.
        <ptr> --> <hdr><n><char_1><char_2>....<char_n><0>
    '''  
    name = 'string'
    
    def __init__(self):
        DynamicArray.__init__(self,Char())
    
    def alloc(self,emitter,length):
        # Allocate one extra char for null at the end
        DynamicArray.alloc(self,emitter,length+1)
        self.length = length
        self.set_length(emitter,self.length)
        
    def load_literal(self,emitter,literal):
        self.alloc(emitter,len(literal))
        index = 0
        for ch in literal:
            emitter.store_imm_byte_at(index+self.header_size,ord(ch))
            index += 1
        emitter.store_imm_byte_at(index+self.header_size,0)
        
    
    def load_c_string(self,emitter):
        emitter.add_imm_to_pointer(self.header_size)
    
class IntegralOps:

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
        
        
class Int(BasicType,IntegralOps):

    name = 'int'

    def __init__(self):
        self.sizeof = WORD
        self.stack_size = 1        

    def load_literal(self,emitter,literal):
        emitter.load_imm_int(literal)

    def store_at(self,emitter,offset=0):
        emitter.store_acc_int_at(offset)
        
    def load_at(self,emitter,offset=0):
        emitter.load_acc_int_at(offset)

class Char(BasicType,IntegralOps):

    name = 'char'

    def __init__(self):
        self.sizeof = 1
        self.stack_size = 1
        
    def load_literal(self,emitter,literal):
        emitter.load_imm_int(ord(literal))

    def store_at(self,emitter,offset=0):
        emitter.store_acc_byte_at(offset)
        
    def load_at(self,emitter,offset=0):
        emitter.load_acc_byte_at(offset)
        
