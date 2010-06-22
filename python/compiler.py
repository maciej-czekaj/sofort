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
    
    def __contains__(self,name):
        return name in self.vars
        
    def add(self,var):
        self.vars[var.name] = var
        var.stack_index = self.stack_size
        self.stack_size += var.type.stack_size
        
    def __getitem__(self,name):
        return self.vars[name]


OPERATIONS = {
    '+' : 'add',
    '-' : 'sub',
    '/' : 'div',
    '*' : 'mul',
    '<' : 'lt',
    '>' : 'gt',
    '<=' : 'le',
    '>=' : 'ge',
    '==' : 'eq',
    '!=' : 'ne',
}

RELOPS = {
    '<' : 'lt',
    '>' : 'gt',
    '<=' : 'le',
    '>=' : 'ge',
    '==' : 'eq',
    '!=' : 'ne',
}


        
class Parser:

    def __init__(self,scanner,emitter):
        self.scanner = scanner
        self.emitter = emitter
        self.next()
        self.stack = []
        
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
        self.emitter.begin_prog()
        self.emitter.begin_func('main')
        self.stack.append(Locals())
        while self.token is not EOF:
            self.Statement()
            #self.emitter.print_int()
        if self.token is not EOF:
            raise ParserException('EOF')
        del self.stack[-1]
        self.emitter.end_func()        
        self.emitter.end_prog()
        
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
        self.Expression()
        self.emitter.print_int()

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
        id = self.token.value
        locals = self.stack[-1]
        self.next()
        self.expect('=')
        type = self.Expression()
        if not id in locals:
            var = LocalVar(id,type)
            locals.add(var)
            self.emitter.alloca(WORD*locals.stack_size)
        else:
            var = locals[id]
            if not var.type.typeof(type):
                raise ParserException('Illegal assignment of %s to variable %s' % (str(type),str(var.type)))
        # The type of a variable may change in the future
        # when a constant is promoted to non constant value.
        var.store(self.emitter) #self.emitter.store_var_int(locals[id])

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
            var = self.get_var(self.token.value)
            var.load(self.emitter)
            self.next()
            return var.type
        elif isinstance(self.token,int):
            type = Int()
            type.load_literal(self.emitter,self.token) #self.emitter.load_imm_int(self.token)
            self.next()
            return type
        elif self.match('('):
            type = self.Expression()
            self.expect(')')
            return type
        else:
            raise ParserException('Unexpected token %s' % str(self.token))

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
    parser = Parser(scanner,Emitter(asm))
    #import echo
    #echo.echo_class(Parser)
    parser.Top()
    asm.close()
    src.close()
    #do_gcc(asmfile,binfile)
    
def testScanner1():
    f = StringIO('abc / 123 +cd*1')
    scanner = Scanner(f)
    exp = ['abc','/',123,'+','cd','*',1]
    res = []
    token = scanner.scan()
    while token != EOF:
        res.append(token)
        token = scanner.scan()
    #print res,exp
    assert res == exp
    
if __name__ == '__main__':
    main()
