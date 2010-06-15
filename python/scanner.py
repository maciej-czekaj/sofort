
class ScannerException(Exception):
    
    def __init__(self,char,file=None,line=None):
        Exception.__init__(self,'Illegar char %s' % repr(char))

# Tokens

digits = list('0123456789')
    
letters = map(chr,range(ord('a'),ord('z')+1)) + map(chr,range(ord('A'),ord('Z')+1))

whitespace = list(" \t\n\r")
    
operands = list('+-*/=<>')

parens = list('(){}')


ops_or_parens = operands + parens

EOF = []

keywords = set(['if','while','else','print'])

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


class Scanner:
    
    def __init__(self,file):
        self.token = None
        self.file = file
        self.line = 1
        self.col = 0
        self.buffer = []
        self.getchar()
        
    def pos(self):
        return self.file.name,self.line,self.col,''.join(self.buffer)
        
    def getchar(self):
        self.char = self.file.read(1)
        self.col += 1
        self.buffer.append(self.char)

    def skipwhite(self):
        while self.char in whitespace:
            if self.char == "\n":
                self.line += 1
                self.col = 0
                self.buffer = []
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
