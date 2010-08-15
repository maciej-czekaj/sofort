#!/usr/bin/env python
import sys
from StringIO import StringIO
from os.path import basename
import re
from subprocess import check_call

from emitter import *
from scanner import *
from sofortTypes import *


class ParserException(Exception):
    
    def __init__(self,msg,file='',line='',col='',buffer=None):
        s = '%s:%s:%s: %s' % (file,line,col,msg)
        if buffer:
            s += "\n" + buffer
        Exception.__init__(self,s)


class LocalVar:
    
    def __init__(self,name,type):
        self.name = name
        self.type = type
        #stack_index is assigned by Locals object
    
    def store(self,emitter):
        self.type.store(emitter,self.stack_index)
        
    def load(self,emitter):
        self.type.load(emitter,self.stack_index)

class Locals:
    
    def __init__(self):
        self.stack_size = 0
        self.vars = {}
        self.get = self.vars.get
    
    def __contains__(self,name):
        return name in self.vars
        
    def add(self,var):
        self.vars[var.name] = var
        var.stack_index = self.stack_size
        self.stack_size += var.type.stack_size
        
    def __getitem__(self,name):
        return self.vars[name]


OPS = {
    '+' : 'add',
    '-' : 'sub',
    '/' : 'div',
    '*' : 'mul',
}

RELOPS = {
    '<' : 'lt',
    '>' : 'gt',
    '<=' : 'le',
    '>=' : 'ge',
    '==' : 'eq',
    '!=' : 'ne',
}

PRIMITIVE_TYPES = set(['int','char','string'])

class Location:

    def __init__(self,type,store_func):
        self.type = type
        self.store = store_func


TYPE_MAP = {
    'int' : Int,
    'char' : Char,
    'string' : String,
    '[' : DynamicArray,
}
        
class ASTParser:
    ''' Parses AST tree and produces Simple-IR
    '''

    def __init__(self,ast):
        self.root = ast
        self.out = sys.stdout
    
    def parse(self):
        for func in self.root:
            self.visit_func(func)
    
    def visit_func(self,func):
        assert func[0] == 'FUNC'
        _f,name,ret_type,params,block = func
        ret_type = self.Type(ret_type)
        func_params = [] # TODO
        body = self.visit_func_block(block)
        func_hdr = ('func',name,ret_type.ir_type,func_params)
        
        
    def Type(self,type):
        typelist = type[1]
        type = TYPE_MAP[typelist[-1]]() # Construct the type
        for t in reverse(typelist[:-1]):
            if t != '[':
                raise ParserException('Illegal type %s' % str(type))
            type = DynamicArray(type)
        return type
    
class SofortParser:

    def __init__(self,scanner):
        self.scanner = scanner
        self.namespace = Namespace()
        self.next()

    def next(self):
        self.token = self.scanner.scan()
        return self.token

    def match(self,tok):
        if self.token == tok:
            self.next()
            return True
        return False

    def expect(self,tok):
        #print self.token
        if self.token != tok:
            raise ParserException('Expected "%s"'%tok,*self.scanner.pos())
        return self.next()

    def Top(self):
        try:
            return self._Top()
        except :
            print self.scanner.pos()
            raise #ParserException('Error :%s' % str(e),*self.scanner.pos())

    def _Top(self):
        stat_list = []
        self.namespace.begin_scope()
        while self.token is not EOF:
            stat_list.append( self.Statement() )
        if self.token is not EOF:
            raise ParserException('EOF')
        return [('FUNC','main',('TYPE',['int']),[],('BLOCK',stat_list))]
            
    def Statement(self):
        if isinstance(self.token,Ident):
            stat = self.Assignment()
        elif self.token == 'print':
            stat = self.Print()
        elif self.token == 'if':
            stat = self.If()
        elif self.token == 'while':
            stat = self.While()
        elif self.token == '{':
            stat = self.Block()
        else:
            raise ParserException('Expected statement',*self.scanner.pos())
        #print stat
        return stat

    def While(self):
        self.next()
        expr = self.Expression()
        stat = self.Statement()
        return 'WHILE',expr,stat

    def Block(self):
        self.next()
        stats = []
        while not self.match('}'):
            stats.append( self.Statement() )
        return 'BLOCK',stats
        
    def Print(self):
        self.next()
        expr = self.Expression()
        return 'PRINT',expr
        
    def If(self):
        self.next()
        expr = self.Expression()
        stat1 = self.Statement()       
        if self.match('else'):
            stat2 = self.Statement()
            return 'IFELSE',expr,stat1,stat2
        return 'IF',expr,stat1

    def Assignment(self):
        ''' Assignment acts as both declaration and ordinary assignment.
            x = <Expr>
            If x is first used, it is declaration of var x of type(Expr).
            Otherwise, it is ordinary assignment where type(x) must match type(Expr).
        '''
        lval = self.Lvalue()
        self.expect('=')
        expr = self.Expression()
        var = lval[1]
        if self.namespace.get_var(var):
            return 'ASSIGN',lval,expr
        self.namespace.add_var(var)
        return 'ASSIGN_NEW',lval,expr
 
    def Lvalue(self):
        id = self.token.value
        self.next()
        if self.match('['):
            index = self.Expression()
            self.expect(']')
            return 'INDEX',id,index
        return 'ID',id

    def Expression(self):
        return self.RelationalExpression()
        
    def RelationalExpression(self):
        left = self.ArithmeticExpression()
        while True:
            op = RELOPS.get(self.token,None)
            if not op:
                break
            self.next()
            right = self.ArithmeticExpression()
            left = ('RELOP',op,left,right)
        return left
        
        
    def ArithmeticExpression(self):
        left = self.Product()
        while True:
            if self.token == '+':
                op = 'add'
            elif self.token == '-':
                op = 'sub'
            else:
                break
            self.next()
            right = self.Product()
            left = ('ARITH',op,left,right)
        return left
        
    def Product(self):
        left = self.Factor()
        while True:
            if self.token == '*':
                op = 'mul'
            elif self.token == '/':
                op = 'div'
            else:
                break
            self.next()
            right = self.Factor()
            left = ('ARITH',op,left,right)
        return left

    def Factor(self):
        if self.match('-'):  # unary minus
            expr = self.UnaryExpression()
            expr = ('NEG',expr)
        else:
            expr = self.UnaryExpression()
        return expr        

    def UnaryExpression(self):
        if isinstance(self.token,Ident):
            expr = self.VarOrFunc()
        elif isinstance(self.token,int):
            expr = ('INT',self.token)
            self.next()
        elif isinstance(self.token,CharLiteral):
            expr = ('CHAR',self.token.value)
            self.next()
        elif isinstance(self.token,StringLiteral):
            expr = ('STRING',self.token.value)
            self.next()
        elif self.match('('):
            expr = self.Expression()
            self.expect(')')
        elif self.match('['):
            expr = self.ArrayConstructor()
        else:
            raise ParserException('Unexpected token %s' % str(self.token))
        return expr

    def VarOrFunc(self):
        var = self.token.value
        self.check_var(var)
        self.next()
        if self.match('['): # array element
            index = self.Expression()
            self.expect(']')
            return 'INDEX',var,index
        return 'ID',var
        
            
    def ArrayConstructor(self):
        if self.match(']'):
            # Zero-length array
            # Still a small space is allocated in case of further expansion.
            arr_subtype = self.Type()
            return 'ARRAY_INIT',arr_subtype
        init_list = []
        init_list.append( self.Expression() )
        # Now we know the array's subtype
        while not self.match(']'):
            self.expect(',')
            # allow for extra ',' at the end
            if self.match(']'):
                break;
            init_list.append( self.Expression() )
        return 'ARRAY_CONS',init_list
        
    def Type(self):
        type_desc = []
        while self.match('[]'):
            type_desc.append('[')
        if self.token in PRIMITIVE_TYPES:
            type_desc.append( self.token.value )
        else:
            raise ParserException('Expected type, found %s' % str(self.token),*self.scanner.pos())
        self.next()
        return ('TYPE',type_desc)

    def check_var(self,name):
        if not self.namespace.get_var(name):
            raise ParserException('Unknown variable %s' % name,*self.scanner.pos())


class Namespace:

    def __init__(self):
        self.scope = []
        
    def get_var(self,name):
        for s in reversed(self.scope):
            var = s.get(name)
            if var:
                return var
        return None

    def add_var(self,name,var=True):
        self.scope[-1][name] = var
        
    def begin_scope(self):
        self.scope.append({})
        
    def end_scope(self):
        del self.scope[-1]


class Parser:

    def __init__(self,scanner):
        self.scanner = scanner
        self.next()
        self.stack = []
        self.emitter_stack = []
        
    def next(self):
        self.token = self.scanner.scan()
        return self.token

    def Top(self):
        try:
            self._Top()
        except :
            print self.scanner.pos()
            raise #ParserException('Error :%s' % str(e),*self.scanner.pos())

    def _Top(self):
        self.push_emitter()
        self.constants = Constants()
        program = Emitter()
        program.begin_prog()
        self.func = Func('main')
        self.stack.append(Locals())
        while self.token is not EOF:
            self.Statement()
        if self.token is not EOF:
            raise ParserException('EOF')
        del self.stack[-1]
        program.emit_block(self.constants.block())
        program.emit_block(self.func.block(self.emitter.buffer)) 
        self.emitter = program
        
    def match(self,tok):
        if self.token == tok:
            self.next()
            return True
        return False
        
    def expect(self,tok):
        if self.token != tok:
            raise ParserException('Expected "%s"'%tok,*self.scanner.pos())
        return self.next()
        
    def Statement(self):
        if isinstance(self.token,Ident):
            self.Assignment()
        elif self.token == 'print':
            self.Print()
        elif self.token == 'if':
            self.If()
        elif self.token == 'while':
            self.While()
        elif self.token == '{':
            self.Block()
        else:
            raise ParserException('Expected statement',*self.scanner.pos())

    def While(self):
        self.next()
        label_loop = self.emitter.new_label()
        self.emitter.label(label_loop)
        label_exit = self.emitter.new_label()
        self.Expression()
        self.emitter.jump_if_false(label_exit)
        self.Statement()
        self.emitter.jump(label_loop)
        self.emitter.label(label_exit)
        
    def Block(self):
        self.next()
        while not self.match('}'):
            self.Statement()

    def Print(self):
        #assert self.token.name == 'print'
        self.next()
        type = self.Expression()
        if isinstance(type,Int):
            self.emitter.print_int()
        elif isinstance(type,Char):
            self.emitter.print_char()
        elif isinstance(type,String):
            type.load_c_string(self.emitter)
            self.emitter.print_string()
        else:
            raise ParserException('Unsupported type',*self.scanner.pos())
            
    def If(self):
        self.next()
        self.Expression()
        label1 = self.emitter.new_label()
        self.emitter.jump_if_false(label1)
        self.Statement()       
        if self.match('else'):
            label2 = self.emitter.new_label()
            self.emitter.jump(label2)
            self.emitter.label(label1)
            self.Statement()
            label1 = label2 # emit label2 below instead of label1
        self.emitter.label(label1)
        
    def Assignment(self):
        ''' Assignment acts as both declaration and ordinary assignment.
            x = <Expr>
            If x is first used, it is declaration of var x of type(Expr).
            Otherwise, it is ordinary assignment where type(x) must match type(Expr).
        '''
        id,location = self.Lvalue()
        locals = self.stack[-1]
        self.expect('=')
        rtype = self.Expression()
        if not location:
            var = LocalVar(id,rtype)
            locals.add(var)
            self.func.set_stack(WORD*locals.stack_size)
            location = var
        else:
            if not location.type.typeof(rtype):
                raise ParserException('Illegal assignment of %s to variable %s' % (str(rtype),str(ltype)))
                # The type of a variable may change in the future
        # when a constant is promoted to non constant value.
        location.store(self.emitter) #self.emitter.store_var_int(locals[id])

    def Lvalue(self):
        id = self.token.value
        self.next()
        if self.match('['):
            var = self.get_var(id)
            self.assert_typeof(var.type,Array)
            var.load(self.emitter)
            index_type = self.Expression()
            self.assert_typeof(index_type,Int,'Array index must be int')
            self.expect(']')
            var.type.add_offset(self.emitter)
            location = Location(var.type.subtype,var.type.store_at)
            return id,location
        locals = self.stack[-1]
        var = locals.get(id)
        if var:
            return id,var
        return id,None
            
    def assert_typeof(self,obj,type,err_msg=''):
        type = type()
        if not obj.typeof(type):
            raise ParserException('Expected type "%s", not "%s". %s' % 
                (str(obj),str(type),err_msg),*self.scanner.pos())
        
    def Expression(self):
        return self.RelationalExpression()
        
    def RelationalExpression(self):
        left = self.ArithmeticExpression()
        while True:
            op = RELOPS.get(self.token,None)
            if not op:
                break
            left.push(self.emitter)
            self.next()
            right = self.ArithmeticExpression()
            self.check_op(left,right,op)
            self.do_operation(right,op)
            left = left.union(right)
        return left
        
        
    def ArithmeticExpression(self):
        left_type = self.Product()
        while True:
            if self.token == '+':
                op = 'add'
            elif self.token == '-':
                op = 'sub'
            else:
                break
            left_type.push(self.emitter)
            self.next()
            right_type = self.Product()
            self.check_op(left_type,right_type,op)
            self.do_operation(right_type,op)
            left_type = left_type.union(right_type)
        return left_type
            
    def Product(self):
        left_type = self.Factor()
        while True:
            if self.token == '*':
                op = 'mul'
            elif self.token == '/':
                op = 'div'
            else:
                break
            left_type.push(self.emitter)
            self.next()
            right_type = self.Factor()
            self.check_op(left_type,right_type,op)
            self.do_operation(right_type,op)
            left_type = left_type.union(right_type)
        return left_type

    def Factor(self):
        if self.match('-'):  # unary minus
            type = self.UnaryExpression()
            self.do_operation(type,'neg')
        else:
            type = self.UnaryExpression()
        return type
            
    def UnaryExpression(self):
        if isinstance(self.token,Ident):
            return self.VarOrFunc()
        elif isinstance(self.token,int):
            type = Int()
            type.load_literal(self.emitter,self.token) #self.emitter.load_imm_int(self.token)
            self.next()
            return type
        elif isinstance(self.token,CharLiteral):
            type = Char()
            type.load_literal(self.emitter,self.token.value)
            self.next()
            return type
        elif isinstance(self.token,StringLiteral):
            type = String()
            type.load_literal(self.emitter,self.token.value)
            self.next()
            return type
        elif self.match('('):
            type = self.Expression()
            self.expect(')')
            return type
        elif self.match('['):
            return self.ArrayConstructor()
        else:
            raise ParserException('Unexpected token %s' % str(self.token))

    def VarOrFunc(self):
            var = self.get_var(self.token.value)
            var.load(self.emitter)
            self.next()
            if self.match('['): # array element
                type = self.Expression()
                array = var.type
                if not type.typeof(Int()):
                    raise ParserExpression('Array index must be int',*self.scanner.pos())
                array.add_offset(self.emitter)
                array.load_at(self.emitter)
                self.expect(']')
                return array.subtype
            return var.type
        
            
    def ArrayConstructor(self):
        if self.match(']'):
            # Zero-length array
            # Still a small space is allocated in case of further expansion.
            arr_subtype = self.Type()
            array_type = DynamicArray(arr_subtype)
            array_type.alloc(self.emitter,8) # make space for 8 elements
            array_type.set_length(self.emitter,0)
            return array_type
        self.push_emitter()
        arr_subtype = self.Expression()
        # Now we know the array's subtype
        array_type = DynamicArray(arr_subtype)
        type = arr_subtype
        length = 1
        array_type.store_at(self.emitter,0)
        while not self.match(']'):
            self.expect(',')
            # allow for extra ',' at the end
            if self.match(']'):
                break;
            type = self.Expression()
            if not arr_subtype.typeof(type):
                raise ParserException('Type mismatch in array constructor:  %s and %s.' % 
                    (arr_type,type))
            array_type.store_at(self.emitter,length)
            length += 1
        array_init = self.pop_emitter()
        # Now we need to load an array
        array_type.alloc(self.emitter,length)
        array_type.set_length(self.emitter,length)
        self.emitter.emit_block(array_init.buffer)
        return array_type
        
    def Type(self):
        if self.match('int'):
            return Int()
        else:
            raise ParserException('Expected type, found %s' % str(self.token),*self.scanner.pos())
        
    def do_operation(self,type,operation):
            op = type.get_operation(operation)
            if op:
                op(self.emitter)
            else:
                raise ParserException('Operation "%s" not supported by type "%s"' % (operation,type))
            
    def get_var(self,name):
        try:
            return self.stack[-1][name]
        except KeyError:
            raise ParserException('Unknown variable %s' % name)
    
    def check_op(self,left,right,op):
        if not left.typeof(right):
            msg = 'Incompatible types in %s %s %s' % (left,op,right)
            raise ParserException(msg,*self.scanner.pos())

    def push_emitter(self):
        e = Emitter()
        self.emitter_stack.append(e)
        self.emitter = e

    def pop_emitter(self):
        e = self.emitter
        del self.emitter_stack[-1]
        self.emitter = self.emitter_stack[-1]
        return e
        
def outputfiles(fname):
    fname = basename(fname)
    base = re.sub('.sofort$','',fname)
    return base + '.s',base

def do_gcc(asm_file,output):
    cmd = "gcc -o %s %s" % (output,asm_file)
    process = check_call(cmd, shell=True)
    
def main():
    if len(sys.argv) == 2:
        src = open(sys.argv[1],'rb')
        asmfile,binfile = outputfiles(src.name)
        asm = open(asmfile,'wb')
    else:
        src = sys.stdin
        asm = sys.stdout
    scanner = Scanner(src)
    parser = SofortParser(scanner)
    #import echo
    #echo.echo_class(SofortParser)
    ast = parser.Top()
    #parser.emitter.flush(asm)
    import pprint
    pprint.pprint(ast)
    asm.close()
    src.close()
    #do_gcc(asmfile,binfile)
    
    
if __name__ == '__main__':
    main()
