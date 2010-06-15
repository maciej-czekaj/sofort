#!/usr/bin/env python
import sys
from StringIO import StringIO

from emitter import *


class ScannerException(Exception):
    
    def __init__(self,char,file=None,line=None):
        Exception.__init__(self,'Illegar char %s' % repr(char))

class ParserException(Exception):
    
    def __init__(self,msg,file='',line=''):
        Exception.__init__(self,'%s:%s: %s' % (file,line,msg))



digits = list('0123456789')
    
letters = map(chr,range(ord('a'),ord('z')+1)) + map(chr,range(ord('A'),ord('Z')+1))

whitespace = list(" \t\n\r")
    
operands = list('+-*/=<>')

parens = list('(){}')


ops_or_parens = operands + parens

EOF = []

keywords = set(['if','while','else','print'])

WORD = 4

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

# Tokens

class Token:
    pass

class StringLiteral(Token):

    def __init__(self,literal):
        self.value = literal


class IntLiteral(Token):

    def __init__(self,literal):
        self.value = literal
        
class Word(Token):

    def __init__(self,name):
        self.value = name

    def __eq__(self,other):
        try:
            return self.value == other or self.value == other.value
        except AttributeError:
            return False
    
    def __str__(self):
        return str(self.value)

class Ident(Word):

    def __init__(self,name):
        Word.__init__(self,name)

class Keyword(Word):
    
    def __init__(self,name):
        Word.__init__(self,name)

# Types

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

class Type:
    
    def __str__(self):
        return self.name
        
    def __eq__(self,other):
        return isinstance(self,other.__class__)

    def __ne__(self,other):
        return not isinstance(self,other.__class__)

    @classmethod
    def get_operation(cls,operation):
        opname = 'op_'+operation
        return getattr(cls,opname,None)


class ComplexType(Type):
    ''' 
    Complex type is represented as a structure and is larger than signle machine word.
    It is __always__ kept on the stack and registers are used to keep only it's address.
    Is should be aligned to machine word boundary.
    We assume that complex variable's address is stored in esi
    as opposed to basic type store in eax. Thus indirect loads and stores do not affect
    direct ones as much. Moreover, it simplifies code generation since we have one default register 
    for indirect access.
    '''

    def store(self,emitter,stack_index):
        # No direct stores of complex types
        pass

    def load(self,emitter,stack_index):
        # Load pointer to structure
        emitter.load_pointer(stack_index)        

    def push(self,emitter):
        ''' Copy contents of complex variable to the top of the stack.
            Example: 
                     movl (%esi),%eax # edx points to a variable
                     pushl %eax
                     movl 4(%esi),%eax
                     pushl %eax
        '''
        emitter.push_complex(self.stack_size)
        

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
    
class String(ComplexType):
    # struct string { char * arr; int len; }
    
    name = 'string'
    
    def __init__(self,literal=None):
        self.literal = literal
        self.sizeof = 2*WORD
        self.stack_size = 2

class StringConstant(String):

    def __init__(self,literal):
        String.__init__(self,literal)
        
class Int(BasicType):

    name = 'int'
    supported_operations = 'add sub div mul lt gt le ge eq ne'.split()

    def __init__(self,literal=None):
        self.literal = literal
        self.sizeof = WORD
        self.stack_size = 1
        
    def op_neg(self,emitter):
        emitter.neg_acc_int()
        
    
class IntConstant(Int):
    
    def __init__(self,literal):
        Int.__init__(self,literal)
    
    def load(self,emitter):
        emitter.load_imm_int(literal)

IntConstant.store = None # unsupported operation

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
        
    
        
class Scanner:
    
    def __init__(self,file):
        self.token = None
        self.file = file
        self.line = 1
        self.col = 0
        self.getchar()
        
    def getchar(self):
        self.char = self.file.read(1)
        self.col += 1

    def skipwhite(self):
        while self.char in whitespace:
            if self.char == "\n":
                self.line += 1
            self.getchar()
    
    def scan(self):
        self.skipwhite()
        if self.char in digits:
            return self.scanNumber()
        elif self.char in letters:
            return self.scanIdentifier()
        elif self.char in ['<','>']:
            token = self.char 
            self.getchar()
            if self.char == '=':
                token = token + '='
                self.getchar()
            return token
        elif self.char in ops_or_parens:
            token = self.char 
            self.getchar()
            return token
        elif self.char == '':
            return EOF
        else:
            raise ScannerException(self.char)

    def scanEscapeSeq(self):
        self.getchar()
        if self.char == '\\':
            char = '\\'
        elif self.char == 'n':
            char = '\n'
        elif self.char == 't':
            char = '\t'
        elif self.char == '"':
            char = '"'
        else:
            char = '\\' + self.char
        self.getchar()
        return char
            
    def scanStringLiteral(self):
        self.getchar()
        chars = []
        while self.char != '"':
            if self.char == '\\':
                chars.append(self.scanEscapeSeq())
            else:
                chars.append(self.char)
                self.getchar()
        self.getchar() # '"'
        string = ''.join(chars)
        return StringLiteral(string)
        
    def scanNumber(self):
        s = self.char
        self.getchar()
        while self.char in digits:
            s += self.char
            self.getchar()
        return int(s)
        
    def scanIdentifier(self):
        id = [self.char]
        self.getchar()
        while self.char in letters:
            id.append(self.char)
            self.getchar()
        id = ''.join(id)
        if id in keywords:
            return Keyword(id)
        else:
            return Ident(id)

        
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
        self.emitter.begin_prog()
        self.emitter.begin_func('_main')
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
            raise ParserException(tok)
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
            raise ParserException('statement')

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
            if var.type != type:
                raise ParserException('Illegal assignment of %s to variable %s' % (str(type),str(var.type)))
        var.store(self.emitter) #self.emitter.store_var_int(locals[id])

    def Expression(self):
        self.RelationalExpression()
        return Int()
        
    def RelationalExpression(self):
        self.ArithmeticExpression()
        while True:
            if self.token == '<':
                emit = self.emitter.pop_lt_int
            elif self.token == '>':
                emit = self.emitter.pop_gt_int
            elif self.token == '<=':
                emit = self.emitter.pop_le_int
            elif self.token == '>=':
                emit = self.emitter.pop_ge_int
            else:
                break
            self.emitter.push_acc()
            self.next()
            self.ArithmeticExpression()
            emit()
        
        
    def ArithmeticExpression(self):
        self.Product()
        while True:
            if self.token == '+':
                emit = self.emitter.pop_add_int
            elif self.token == '-':
                emit = self.emitter.pop_sub_int
            else:
                break
            self.emitter.push_acc()
            self.next()
            self.Product()
            emit()
            
    def Product(self):
        self.Factor()
        while True:
            if self.token == '*':
                emit = self.emitter.pop_mul_int
            elif self.token == '/':
                emit = self.emitter.pop_div_int
            else:
                break
            self.emitter.push_acc()
            self.next()
            self.Factor()
            emit()

    def Factor(self):
        if self.match('-'):  # unary minus
            type = self.UnaryExpression()
            self.do_operation(type,'neg')
            #self.emitter.neg_acc_int()
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
            type = IntConstant(self.token)
            type.load(self.emitter) #self.emitter.load_imm_int(self.token)
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
                raise ParserExpression('Operation "%s" not supported by type "%s"' % (operation,type))
            
    def get_var(self,name):
        try:
            return self.stack[-1][name]
        except KeyError:
            raise ParserException('Unknown variable %s' % name)


def main():
    scanner = Scanner(sys.stdin)
    parser = Parser(scanner,Emitter())
    #import echo
    #echo.echo_class(Parser)
    parser.Top()
    
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
