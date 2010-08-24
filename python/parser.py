
from scanner import AppException

class ParserException(AppException):
    
    def __init__(self,msg,file='',line='',col='',buffer=None):
        s = '%s:%s:%s: %s' % (file,line,col,msg)
        if buffer:
            s += "\n" + buffer
        Exception.__init__(self,s)


class ASTTuple(tuple):
    pass

    
def ASTNode(tp,text=None):
        t = ASTTuple(tp)
        t.text = text
        return t


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
        first_line = self.scanner.line
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
        #text=self.scanner.content[first_line]
        return ASTNode(stat,first_line)

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
        return 'DECLARE',lval,expr
 
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
