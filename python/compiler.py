#!/usr/bin/env python
import sys
from StringIO import StringIO

from emitter import *

class ScannerException(Exception):
    
    def __init__(self,char,file=None,line=None):
        Exception.__init__(self,'Illegar char %s' % repr(char))

class ParserException(Exception):
    
    def __init__(self,tok,file=None,line=None):
        Exception.__init__(self,'Expected %s' % repr(tok))



digits = list('0123456789')
    
letters = map(chr,range(ord('a'),ord('z')+1)) + map(chr,range(ord('A'),ord('Z')+1))

whitespace = list(" \t\n\r")
    
operands = list('+-*/=<>')

parens = list('(){}')


ops_or_parens = operands + parens

EOF = []

keywords = set(['if','while','else','print'])

class Word:

    def __init__(self,name):
        self.value = name

    def __eq__(self,other):
        try:
            return self.value == other or self.value == other.value
        except AttributeError:
            return False

class Ident(Word):

    def __init__(self,name):
        Word.__init__(self,name)

class Keyword(Word):
    
    def __init__(self,name):
        Word.__init__(self,name)


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
            return self.scanDigit()
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
        
    def scanDigit(self):
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
        self.emitter.prog_prologue()
        self.emitter.begin_func('_main')
        self.stack.append({}) # locals
        while self.token is not EOF:
            self.Statement()
            #self.emitter.print_int()
        if self.token is not EOF:
            raise ParserException('EOF')
        del self.stack[-1]
        self.emitter.end_func()        
        
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
        id = self.token.value
        locals = self.stack[-1]
        self.next()
        self.expect('=')
        self.Expression()
        if not locals.has_key(id):
            locals[id] = len(locals)
            self.emitter.alloca(4*len(locals))
        self.emitter.store_var_int(locals[id])

    def Expression(self):
        self.RelationalExpression()
        
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
            self.UnaryExpression()
            self.emitter.neg_acc_int()
        else:
            self.UnaryExpression()
    
    def UnaryExpression(self):
        if isinstance(self.token,Ident):
            self.emitter.load_var_int(self.get_var(self.token.value))
            self.next()
        elif isinstance(self.token,int):
            self.emitter.load_imm_int(self.token)
            self.next()
        elif self.match('('):
            self.Expression()
            self.expect(')')
        else:
            raise ParserException('factor')

    def get_var(self,name):
        try:
            return self.stack[-1][name]
        except KeyError:
            raise ParserException('variable')


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
