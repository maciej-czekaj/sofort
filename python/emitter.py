from sys import platform as PLAT

if PLAT!='linux':
    mangle=lambda(s): '_'+s
else:
    mangle=lambda(s): s


PROG_PROLOGUE=r"""
.data
int_format:
	.asciz "%d\n"  # format string for printf
char_format:
	.asciz "%c\n"  
string_format:
	.asciz "%s\n" 
"""

FUN_PROLOGUE="""
.text
.globl %s
%s:
	pushl	%%ebp
	movl	%%esp,%%ebp
	subl	$%d,%%esp   # locals
"""

STACKALIGN=r"""
	andl	$-16, %esp # align stack to 16 byte boundary needed for floating point
"""

FUN_EPILOGUE=r"""
	movl	$0,%eax  # return 0
	leave
	ret
"""

TAB="\t"


# class Block:

    # def __init__(self):
        # self.inst_buffer = []
    
    # def append(self,inst):
        # self.inst_buffer.append(inst)

    # def extend(self,buffer):
        # self.inst_buffer.extend(buffer)
    
    # def emit(self,emit):
        # for inst in self.inst_buffer:
            # emit(inst)
        
            
class Func:

    def __init__(self,name,stack=0):
        self.name = name
        self.stack = stack
    
    def set_stack(self,stack):
        self.stack = stack
        
    # def emit(self,emit):
        # name = mangle(self.name)
        # emit(FUN_PROLOGUE % (name,name,self.stack)) # name,name,stack
        # Block.emit(self,emit)
        # emit(FUN_EPILOGUE)

    def block(self,buffer):
        name = mangle(self.name)
        prologue = FUN_PROLOGUE % (name,name,self.stack)
        return [prologue] + buffer + [FUN_EPILOGUE]         
        
class Constants:

    def __init__(self):
        self.buffer = []
    
    def block(self):
        return ['.data'] + self.buffer
    
    def add_string_constant(self,const):
        self.buffer.append('.asciz "%s"' % const)

        
def stack_offset(index):
    return (index+1)*4

class Emitter:
    
    def __init__(self):
        self.buffer = []
        self.emit_raw = self.buffer.append
        #self.emit_to_file = self.emit_raw
        self.__call__ = self.emit_raw
        self.lbl_num = 0
        #self.constants = Constants(self.emit_raw)
    
    def flush(self,file):
        print >> file, '\n'.join(self.buffer)

    def emit_block(self,buffer):
        self.buffer.extend(buffer)
        
    def emit(self,s):
        s = s.replace(' ',TAB)
        self.emit_raw(TAB + s)
    
    # def begin_func(self,name):
        # self.func = Func(name,0)
        # self.emit_raw = self.emit_to_buffer

    def begin_prog(self):
        self.emit_raw(PROG_PROLOGUE)
        
    # def end_prog(self):
        # self.constants.emit()
        
    # def end_func(self):
        # self.func.emit(self.emit_to_file)
        # self.emit_raw = self.emit_to_file
        # del self.func
        
    # def alloca(self,stack):
        # self.func.set_stack(stack)
        
    def print_int(self):
        self.push_acc()
        self.emit("pushl $int_format")
        self.call('printf',2)

    def print_char(self):
        self.push_acc()
        self.emit("pushl $char_format")
        self.call('printf',2)
        
    def print_string(self):
        self.push_pointer()
        self.emit("pushl $string_format")
        self.call('printf',2)

    def push_imm_int(self,value):
        self.emit("pushl $%d" % value)
        
    def push_acc(self):
        self.emit("pushl %eax")
    
    def push_pointer(self):
        self.emit("pushl %esi")

    def pop_pointer(self):
        self.emit("popl %esi")

    def pop_add_pointer(self):
        self.emit("addl (%esp),%esi")
        self.emit("addl $4,%esp")

    def add_acc_to_pointer(self):
        self.emit("addl %eax,%esi")
        
    def store_acc_int_at(self,index=0):
        self.emit("movl %%eax,%d(%%esi)" % index)

    def store_imm_int_at(self,index,val):
        self.emit("movl $%d,%d(%%esi)" % (val,index))

    def load_acc_int_at(self,index=0):
        self.emit("movl %d(%%esi),%%eax" % index)
        
    def pop_add_int(self):
        self.emit("addl %eax,(%esp)")
        self.emit("popl %eax")
    
    def pop_sub_int(self):
        self.emit("subl %eax,(%esp)")
        self.emit("popl %eax")
        
    def pop_mul_int(self):
        self.emit("imull (%esp)")
        self.emit("addl $4,%esp")
        
    def mul_imm_int(self,value):
        self.emit("imull $%d,%%eax" % value)
        
    def pop_div_int(self):
        self.emit("movl %eax,%ebx")
        self.emit("popl %eax")
        self.emit("cdq") # sign-extend eax into edx:eax needed for division
        self.emit("idivl %ebx")
        
    def load_imm_int(self,value):
        self.emit("movl $%d,%%eax" % value)
        
    def neg_acc_int(self):
        self.emit("negl %eax")
        
    def load_var_int(self,index):
        self.emit("movl -%d(%%ebp),%%eax" % (stack_offset(index),))

    def store_var_int(self,index):
        self.emit("movl %%eax,-%d(%%ebp)" % (stack_offset(index),))
        
    def label(self,label):
        self.emit_raw("%s:" % label)

    def new_label(self):
        label = 'lbl%d' % self.lbl_num
        self.lbl_num += 1
        return label
    
    def jump_if_false(self,label):
        self.emit("orl %eax,%eax")
        self.emit("je %s" % label)

    def jump(self,label):
        self.emit("jmp %s" % label)

    def pop_lt_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setl %al")
        self.emit("movzbl %al,%eax")
        self.emit("addl $4,%esp")

    def pop_gt_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setg %al")
        self.emit("movzbl %al,%eax")
        self.emit("addl $4,%esp")
                
    def pop_le_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setle %al")
        self.emit("movzbl %al,%eax")
        self.emit("addl $4,%esp")
        
    def pop_ge_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setge %al")
        self.emit("movzbl %al,%eax")
        self.emit("addl $4,%esp")

    def move_pointer(self):
        self.emit("movl %eax,%esi")

    def load_var_pointer(self,index):
        self.emit("movl -%d(%%ebp),%%esi" % (stack_offset(index),))

    def store_var_pointer(self,index):
        self.emit("movl %%esi,-%d(%%ebp)" % (stack_offset(index),))
    
    def call(self,func,argc):
        self.emit("call %s" % mangle(func))
        self.emit("addl $%d,%%esp" % (argc*4))
        
    def load_acc_byte_at(self,index=0):
        self.emit("movzxb %d(%%esi),%%eax" % index)
    
    def store_acc_byte_at(self,index=0):
        self.emit("movb %%al,%d(%%esi)" % index)

    def store_imm_byte_at(self,index,val):
        self.emit("movb $%d,%d(%%esi)" % (val,index))

