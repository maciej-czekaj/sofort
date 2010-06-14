
PROG_PROLOGUE=r"""
.section .rdata,"dr"
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
	pushl	%eax
	pushl	$Format
	call	_printf
	subl	$8,%esp
"""

TAB="\t"

class Func:

    def __init__(self,name,stack):
        self.name = name
        self.stack = stack
        self.inst_buffer = []
    
    def set_stack(self,stack):
        self.stack = stack
    
    def append(self,inst):
        self.inst_buffer.append(inst)
    
    def emit(self,emit):
        emit(FUN_PROLOGUE % (self.name,self.name,self.stack)) # name,name,stack
        for inst in self.inst_buffer:
            emit(inst)
        emit(FUN_EPILOGUE)


class Constants:

    def __init__(self,emitter):
        self.entries = []
        self.emitter = emitter
    
    def add(self,const):
        self.entries.append(const)
        
    def emit(self):
        self.emitter('.section .rdata,"dr"')
        for const in self.entries:
            self.emitter(const)

       

class Emitter:
    
    def __init__(self):
        self.emit = self.emit_print
        #self.func = None
        self.lbl_num = 0
        self.constants = Constants(self.emit_ml)
        
    def emit_print(self,s):
        s = s.replace(' ',TAB)
        print TAB + s
    
    def begin_func(self,name):
        self.func = Func(name,0)
        self.emit = self.buffer_func
        
    def buffer_func(self,s):
        self.func.append(s)

    def begin_prog(self):
        self.emit_ml(PROG_PROLOGUE)
        
    def end_prog(self):
        self.constants.emit()
        
    def end_func(self):
        self.func.emit(self.emit_print)
        self.emit = self.emit_print
        del self.func
        
    def alloca(self,stack):
        self.func.set_stack(stack)
        
    def print_int(self):
        self.emit(PRINT_INT)

    def emit_ml(self,s):
        print s
    
    def push_acc(self):
        self.emit("pushl %eax")
    
    def pop_add_int(self):
        self.emit("addl %eax,(%esp)")
        self.emit("popl %eax")
    
    def pop_sub_int(self):
        self.emit("subl %eax,(%esp)")
        
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
        self.emit("%s:" % label)

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
        
    def pop_gt_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setg %al")
        self.emit("movzbl %al,%eax")
                
    def pop_le_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setle %al")
        self.emit("movzbl %al,%eax")
        
    def pop_ge_int(self):
        self.emit("cmpl %eax,(%esp)")
        self.emit("setge %al")
        self.emit("movzbl %al,%eax")

	def load_pointer(self):
		pass
		
    def add_string_constant(self,const):
        self.constants.add('.asciz "%s"' % const)
        
		
