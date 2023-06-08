import os
import uuid
from pylspclient.lsp_structs import TextDocumentItem, TextDocumentIdentifier

class ProofState(object):
    def __init__(self, coq_lsp_client, file_path, ast):
        self.path = file_path
        with open(file_path, "r") as f:
            self.lines = f.read().split('\n')
        self.ast = ast['spans']
        self.coq_lsp_client = coq_lsp_client
        self.current_step = None
        self.in_proof = False
    
    def __get_expr(self, ast_step):
        return ast_step['span']['v']['expr']
    
    def __get_theorem_name(self, expr):
        return expr[2][0][0][0]['v'][1]
    
    def __search(self, keywords, search):
        dir = os.path.dirname(self.path)
        new_base_name = os.path.basename(self.path).split('.')
        new_base_name = new_base_name[0] + \
            f"new{str(uuid.uuid4()).replace('-', '')}." + new_base_name[1]
        new_path = os.path.join(dir, new_base_name)
        with open(new_path, 'w') as f:
            with open(self.path, 'r') as original:
                fmt = ''
                for kw in keywords: fmt += f"\n{kw} {search}."
                f.write(original.read() + fmt)

        res = {}
        with open(new_path, 'r') as f:
            uri = "file://" + new_path
            # FIXME probably we have to change this to a didChange
            # In that way we can use a single file
            self.coq_lsp_client.didOpen(TextDocumentItem(uri, 'coq', 1, f.read()))

            for kw in keywords:
                queries = self.coq_lsp_client.get_queries(TextDocumentIdentifier(uri), kw)
                for query in queries:
                    if query.query == f"{search}":
                        res[kw] = query.results[0]
            self.coq_lsp_client.didClose(TextDocumentIdentifier(uri))
        
        os.remove(new_path)
        return res
    
    def __compute(self, search):
        res = self.__search(('Print', 'Compute'), f"{search}")

        if 'Print' not in res.keys(): return None
        definition = res['Print'].split()
        if 'Compute' not in res.keys(): return ' '.join(definition)
        theorem = res['Compute'].split()
        if theorem[1] == search and definition[1] != search:
            return ' '.join(theorem[1:])
        
        return ' '.join(definition)
    
    def __locate(self, search):
        nots = self.__search(('Locate',), f"\"{search}\"")['Locate'].split('\n')
        fun = lambda x: x.endswith("(default interpretation)")
        if len(nots) > 1: return list(filter(fun, nots))[0][:-25]
        else: return nots[0][:-25] if fun(nots[0]) else nots[0]

    def exec(self, steps=1):
        for _ in range(steps):
            self.current_step = self.ast.pop(0)
            if self.__get_expr(self.current_step)[0] == 'VernacProof':
                self.in_proof = True
            elif self.__get_expr(self.current_step)[0] == 'VernacEndProof':
                self.in_proof = False

    def next_steps(self):
        if not self.in_proof:
            return None

        steps = []
        start_line = self.current_step['range']['end']['line']
        start_character = self.current_step['range']['end']['character']

        for step in self.ast:
            steps.append(step)
            if self.__get_expr(step)[0] == 'VernacEndProof':
                break

        end_line = step['range']['end']['line']
        end_character = step['range']['end']['character']

        curr_text = self.lines[start_line:end_line + 1]
        curr_text[0] = curr_text[0][start_character:]
        curr_text[-1] = curr_text[-1][:end_character + 1]

        return '\n'.join(curr_text), steps
    
    def get_current_theorem(self):
        expr = self.__get_expr(self.current_step)
        if expr[0] != 'VernacStartTheoremProof':
            return None
        name = self.__get_theorem_name(expr)
        return self.__compute(name)
    
    def get_proof_context(self):
        def transverse_ast(el):
            if isinstance(el, dict):
                res = []
                for k, v in el.items():
                    res.extend(transverse_ast(k))
                    res.extend(transverse_ast(v))
                return res
            elif isinstance(el, list) and len(el) == 3 and el[0] == 'Ser_Qualid':
                id = '.'.join([l[1] for l in el[1][1][::-1]] + [el[2][1]])
                search = self.__compute(id)
                return [search] if search else []
            elif isinstance(el, list) and len(el) == 4 and el[0] == 'CNotation':
                return [self.__locate(el[2][1])] + transverse_ast(el[1:])
            elif isinstance(el, list):
                res = []
                for v in el:
                    res.extend(transverse_ast(v))
                return res
            
            return []

        if self.in_proof:
            return transverse_ast(self.next_steps()[1])
        else:
            return None
    
    def jump_to_theorem(self):
        while self.__get_expr(self.current_step)[0] != 'VernacStartTheoremProof': 
            self.exec()
        return self.get_current_theorem()

    def jump_to_proof(self):
        while not self.in_proof: self.exec()