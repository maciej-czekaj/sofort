
class AppException(Exception):
    pass

class ScannerException(AppException):
    def __init__(self,msg,scanner):
        file,line,col,buf = scanner.pos()
        s = '%s:%s:%s: %s' % (file,line,col,msg)
        if buf:
            s += "\n" + buf
        Exception.__init__(self,s)

class IllegalCharException(ScannerException):
    
    def __init__(self,char,scanner):
        ScannerException.__init__(self,'Illegar char %s' % repr(char),scanner)


# Tokens

LINE_COMMENT = '#'

digits = list('0123456789')
    
letters = map(chr,range(ord('a'),ord('z')+1)) + map(chr,range(ord('A'),ord('Z')+1))

whitespace = list(" \t\n\r")
    
operands = list('+-*/=<>')

parens = list('(){}[]')

separators = list(',')

ops_or_parens = operands + parens + separators

EOF = ''

keywords = set(['if','while','else','print'])

class Token:
    
    def __hash__(self):
        return self.value.__hash__()
        
    def __cmp__(self,other):
        return self.value.__cmp__(other.value)


class StringLiteral(Token):

    def __init__(self,literal):
        self.value = literal

    def __eq__(self,other):
        return self.value == other

    def __ne__(self,other):
        return self.value != other
 
class IntLiteral(Token):

    def __init__(self,literal):
        self.value = literal

class CharLiteral(Token):

    def __init__(self,literal):
        self.value = literal    
        
    def __eq__(self,other):
        return self.value == other

    def __ne__(self,other):
        return self.value != other
        
class Word(Token):

    def __init__(self,name):
        self.value = name

    def __eq__(self,other):
        try:
            return self.value == other or self.value == other.value
        except AttributeError:
            return False

    def __ne__(self,other):
        try:
            return self.value != other or self.value != other.value
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
        self.content = [self.buffer]
        self.getchar()
        
    def pos(self):
        return self.file.name,self.line,self.col,''.join(self.buffer)
        
    def getchar(self):
        self.char = self.file.read(1)
        self.col += 1
        self.buffer.append(self.char)

    def nextline(self):
        self.line += 1
        self.col = 0
        self.buffer = []
        self.content.append(self.buffer)
        
    def skipline(self):
        while self.char != '\n':
            self.getchar()
        self.nextline()
        self.getchar()
        
    def skipwhite(self):
        while True:
            if self.char in whitespace:
                if self.char == "\n":
                    self.nextline()
                self.getchar()
            elif self.char == LINE_COMMENT:
                self.skipline()
            else:
                break
                
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
        elif self.char == "'":
            return self.scanCharLiteral()
        elif self.char == '"':
            return self.scanStringLiteral()
        elif self.char == '':
            return EOF
        else:
            raise IllegalCharException(self.char,self)

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
        
    def scanCharLiteral(self):
        self.getchar()
        if self.char == '\\':
            char = self.scanEscapeSeq()
        else:
            char = self.char
        self.getchar()
        if self.char != "'":
            raise ScannerException('Expected "\'", found "%s"' % repr(self.char),self)
        self.getchar()
        return CharLiteral(char)
    
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
