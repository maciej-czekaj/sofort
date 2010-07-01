from sys import platform as PLAT

if PLAT!='linux':
    mangle=lambda(s): '_'+s
else:
    mangle=lambda(s): s


PROG_PROLOGUE=r"""
.data
Format:
	.ascii "%d\n"  # format string for printf
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

PRINT_INT="""
	pushl	%%eax
	pushl	$Format
	call	%s
	subl	$8,%%esp
""" % mangle('printf')

TAB="\t"


class Block:

    def __init__(self):
        self.inst_buffer = []
    
    def append(self,inst):
        self.inst_buffer.append(inst)
        
    def emit(self,emit):
        for inst in self.inst_buffer:
            emit(inst)

class Func(Block):

    def __init__(self,name,stack):
        Block.__init__(self)
        self.name = name
        self.stack = stack
    
    def set_stack(self,stack):
        self.stack = stack
        
    def emit(self,emit):
        name = mangle(self.name)
        emit(FUN_PROLOGUE % (name,name,self.stack)) # name,name,stack
        Block.emit(self,emit)
        emit(FUN_EPILOGUE)


class Constants:

    def __init__(self,emitter):
        self.entries = []
        self.emitter = emitter
    
    def add(self,const):
        self.entries.append(const)
        
    def emit(self):
        self.emitter('.data')
        for const in self.entries:
            self.emitter(const)
           

class Emitter:
    
    def __init__(self,file):
        self.emit_raw = self.emit_to_file
        #self.func = None
        self.lbl_num = 0
        self.constants = Constants(self.emit_raw)
        self.file = file
    
    def begin_block(self):
        self.block = Block()
        self.emit_prev = self.emit_raw
        self.emit_raw = self.block.append
        
    def end_block(self):
        def flush():
            block = self.block
            self.block.emit(self,self.emit_prev)
        self.emit_raw = self.emit_prev
        del self.block
        
    def emit_to_file(self,s):
        print >> self.file, s

    def emit_to_buffer(self,s):
        self.func.append(s)
        
    def emit(self,s):
        s = s.replace(' ',TAB)
        self.emit_raw(TAB + s)
            
    def begin_func(self,name):
        self.func = Func(name,0)
        self.emit_raw = self.emit_to_buffer

    def begin_prog(self):
        self.emit_raw(PROG_PROLOGUE)
        
    def end_prog(self):
        self.constants.emit()
        
    def end_func(self):
        self.func.emit(self.emit_to_file)
        self.emit_raw = self.emit_to_file
        del self.func
        
    def alloca(self,stack):
        self.func.set_stack(stack)
        
    def print_int(self):
        self.emit(PRINT_INT)

    def push_acc(self):
        self.emit("pushl %eax")
    
    def push_pointer(self):
        self.emit("pushl %esi")

    def pop_pointer(self):
        self.emit("popl %esi")

    def pop_add_pointer(self):
        self.emit("addl (%esp),%esi")
        self.emit("addl $4,%esp")

    def store_at(self,index=0):
        self.emit("movl eax,%d(%%esp)" % index)

    def pop_add_int(self):
        self.emit("addl %eax,(%esp)")
        self.emit("popl %eax")
    
    def pop_sub_int(self):
        self.emit("subl %eax,(%esp)")
        self.emit("popl %eax")
        
    def pop_mul_int(self):
        self.emit("imull (%esp)")
        self.emit("addl $4,%esp")
        
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
        self.emit("movl -%d(%%ebp),%%eax" % ((index+1)*4,))

    def store_var_int(self,index):
        self.emit("movl %%eax,-%d(%%ebp)" % ((index+1)*4,))
        
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

    def load_pointer(self):
        pass
        
    def add_string_constant(self,const):
        self.constants.add('.asciz "%s"' % const)
        
