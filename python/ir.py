
IR_TYPES = ['i8','i16','i32','ptr']

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
        func_hdr = ('func',name,ret_type.ir_type,func_params)
        print func_hdr
        body = self.visit_func_block(name,ret_type,func_params,block)
        print body
        
    def Type(self,type):
        typelist = type[1]
        type = TYPE_MAP[typelist[-1]]() # Construct the type
        for t in reversed(typelist[:-1]):
            if t != '[':
                raise ParserException('Illegal type %s' % str(type))
            type = DynamicArray(type)
        return type

    def visit_func_block(name,ret_type,params,block):
        assert block[0] == 'BLOCK'
        stat_list = block[1]
        ir_list = [self.visit(s) for s in stat_list]
        return ir_list
    
    def visit(self,node,*args):
        op = getattr(self,'visit_%s' % node[0])
        return op(self,node,*args)
            
    def visit_ASSIGN(stat):
        lval,expr = stat[1:]
        expr = self.visit(expr)
        #Either z[x] = y or x = y
        # Get lval location
        lval = self.visit(lval)
        # now, direct store or mem store
        store_ir = lval.loc.store(expr.loc)
        return expr.ir + lval.ir + store_ir


class IRNode:
    
    def __init__(self,loc=None,ir=[]):
        self.ir = ir
        self.loc = loc

        
class IRLocation:
    pass
        
class VarLocation(IRLocation):

    def __init__(self,id,type)
        self.id = id
        self.type = type
    
    def store(self,from_loc):
        load_nod = from_loc.load(self.type) 
        return load_nod.ir + CP(load_nod.loc,self)
            
    def load(self):
        return IRNode(self)

class MemLocation(IRLocation):

    def __init__(self,id,offset=0)
        self.id = id
        self.type = type
        self.offset = offset
    
    def store(self,from_loc):
        load_nod = from_loc.load()
        return load_nod.ir + ST(load_nod.loc,self)

    def load(self,type):
        return LD(
#IR        
        
def CP(from_loc,to_loc):
    return [('cp',from_loc.type,from_loc.id,to_loc.id)]
        
def ST(from_loc,to_loc):
    return [('st',from_loc.type,from_loc_id,to_loc.id)]
        
        