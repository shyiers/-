# -*- coding: utf-8 -*-
import re
import sqlparse #0.4.2

#骆驼命名法
import inflection

#词性还原
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer
wnler = WordNetLemmatizer()

#词干提取
from nltk.corpus import wordnet

#############################################################################
OTHER = 0
FUNCTION = 1
BLANK = 2
KEYWORD = 3
INTERNAL = 4

TABLE = 5
COLUMN = 6
INTEGER = 7
FLOAT = 8
HEX = 9
STRING = 10
WILDCARD = 11

SUBQUERY = 12

DUD = 13

ttypes = {0: "OTHER", 1: "FUNCTION", 2: "BLANK", 3: "KEYWORD", 4: "INTERNAL", 5: "TABLE", 6: "COLUMN", 7: "INTEGER",
          8: "FLOAT", 9: "HEX", 10: "STRING", 11: "WILDCARD", 12: "SUBQUERY", 13: "DUD", }

scanner = re.Scanner([(r"\[[^\]]*\]", lambda scanner, token: token), (r"\+", lambda scanner, token: "REGPLU"),
                      (r"\*", lambda scanner, token: "REGAST"), (r"%", lambda scanner, token: "REGCOL"),
                      (r"\^", lambda scanner, token: "REGSTA"), (r"\$", lambda scanner, token: "REGEND"),
                      (r"\?", lambda scanner, token: "REGQUE"),
                      (r"[\.~``;_a-zA-Z0-9\s=:\{\}\-\\]+", lambda scanner, token: "REFRE"),
                      (r'.', lambda scanner, token: None), ])

#---------------------子函数1：代码的规则--------------------
def tokenizeRegex(s):
    # 使用预定义的扫描器对输入字符串进行扫描，并返回标记列表
    results = scanner.scan(s)[0]

    return results

#---------------------子函数2：代码的规则--------------------
class SqlangParser():
    @staticmethod
    def sanitizeSql(sql):
        s = sql.strip().lower()  # 去除首尾空格并转换为小写
        if not s[-1] == ";":  # 如果 SQL 语句末尾没有分号，则添加分号
            s += ';'
        s = re.sub(r'\(', r' ( ', s)  \  # 在左括号前后添加空格
        s = re.sub(r'\)', r' ) ', s)  # 在右括号前后添加空格
        words = ['index', 'table', 'day', 'year', 'user', 'text']  # 定义需要替换的保留字
        for word in words:
            s = re.sub(r'([^\w])' + word + '$', r'\1' + word + '1', s)  # 替换结尾的保留字
            s = re.sub(r'([^\w])' + word + r'([^\w])', r'\1' + word + '1' + r'\2', s)  # 替换中间的保留字
        s = s.replace('#', '')  # 去除井号
        return s

    def parseStrings(self, tok):
        if isinstance(tok, sqlparse.sql.TokenList):
            # 如果 tok 是一个 TokenList，则递归调用 parseStrings 方法处理其子标记
            for c in tok.tokens:
                self.parseStrings(c)
        elif tok.ttype == STRING:
            # 如果 tok 是一个字符串标记
            if self.regex:
                # 如果启用了正则表达式标记化，则使用 tokenizeRegex 方法处理字符串
                tok.value = ' '.join(tokenizeRegex(tok.value))
            else:
                # 否则将字符串替换为 "CODSTR"
                tok.value = "CODSTR"

    def renameIdentifiers(self, tok):
        if isinstance(tok, sqlparse.sql.TokenList):
            # 如果 tok 是一个 TokenList，则递归调用 renameIdentifiers 方法处理其子标记
            for c in tok.tokens:
                self.renameIdentifiers(c)
        elif tok.ttype == COLUMN:
            # 如果 tok 是一个列名标记
            if str(tok) not in self.idMap["COLUMN"]:
                # 如果列名不在 idMap 中，则生成新的列名并添加到 idMap 和 idMapInv 中
                colname = "col" + str(self.idCount["COLUMN"])
                self.idMap["COLUMN"][str(tok)] = colname
                self.idMapInv[colname] = str(tok)
                self.idCount["COLUMN"] += 1
            # 将列名替换为 idMap 中的值
            tok.value = self.idMap["COLUMN"][str(tok)]
        elif tok.ttype == TABLE:
            # 如果 tok 是一个表名标记
            if str(tok) not in self.idMap["TABLE"]:
                # 如果表名不在 idMap 中，则生成新的表名并添加到 idMap 和 idMapInv 中
                tabname = "tab" + str(self.idCount["TABLE"])
                self.idMap["TABLE"][str(tok)] = tabname
                self.idMapInv[tabname] = str(tok)
                self.idCount["TABLE"] += 1
            # 将表名替换为 idMap 中的值
            tok.value = self.idMap["TABLE"][str(tok)]
        elif tok.ttype == FLOAT:
            # 如果 tok 是一个浮点数标记，将其值替换为 "CODFLO"
            tok.value = "CODFLO"
        elif tok.ttype == INTEGER:
            # 如果 tok 是一个整数标记，将其值替换为 "CODINT"
            tok.value = "CODINT"
        elif tok.ttype == HEX:
            # 如果 tok 是一个十六进制数标记，将其值替换为 "CODHEX"
            tok.value = "CODHEX"

    def __hash__(self):
        return hash(tuple([str(x) for x in self.tokensWithBlanks]))

    def __init__(self, sql, regex=False, rename=True):
        # 处理和清理 SQL 语句
        self.sql = SqlangParser.sanitizeSql(sql)

        # 初始化标识符映射和计数器
        self.idMap = {"COLUMN": {}, "TABLE": {}}
        self.idMapInv = {}
        self.idCount = {"COLUMN": 0, "TABLE": 0}
        self.regex = regex

        # 初始化解析树哨兵和表堆栈
        self.parseTreeSentinel = False
        self.tableStack = []

        # 解析 SQL 语句并只保留第一个解析结果
        self.parse = sqlparse.parse(self.sql)
        self.parse = [self.parse[0]]

        # 移除空白字符
        self.removeWhitespaces(self.parse[0])
        # 识别字面量
        self.identifyLiterals(self.parse[0])
        # 设置解析树的类型为子查询
        self.parse[0].ptype = SUBQUERY
        # 识别子查询
        self.identifySubQueries(self.parse[0])
        # 识别函数
        self.identifyFunctions(self.parse[0])
        # 识别表
        self.identifyTables(self.parse[0])

        # 解析字符串
        self.parseStrings(self.parse[0])

        # 如果需要重命名标识符，则进行重命名
        if rename:
            self.renameIdentifiers(self.parse[0])

        # 获取解析后的标记
        self.tokens = SqlangParser.getTokens(self.parse)

    @staticmethod
    def getTokens(parse):
        flatParse = []
        for expr in parse:
            for token in expr.flatten():
                if token.ttype == STRING:
                    flatParse.extend(str(token).split(' '))
                else:
                    flatParse.append(str(token))
        return flatParse

    def removeWhitespaces(self, tok):
        if isinstance(tok, sqlparse.sql.TokenList):
            tmpChildren = []
            for c in tok.tokens:
                if not c.is_whitespace:
                    # 如果标记不是空白字符，将其添加到 tmpChildren 列表中
                    tmpChildren.append(c)

            # 将非空白字符的标记列表赋值回 tok.tokens
            tok.tokens = tmpChildren
            for c in tok.tokens:
                # 递归调用 removeWhitespaces 方法，移除子标记中的空白字符
                self.removeWhitespaces(c)

    def identifySubQueries(self, tokenList):
        isSubQuery = False  # 初始化子查询标志

        for tok in tokenList.tokens:
            if isinstance(tok, sqlparse.sql.TokenList):
                # 递归调用 identifySubQueries 方法，检查子标记列表是否包含子查询
                subQuery = self.identifySubQueries(tok)
                if subQuery and isinstance(tok, sqlparse.sql.Parenthesis):
                    # 如果是子查询且标记为括号类型，则将其类型设置为 SUBQUERY
                    tok.ttype = SUBQUERY
            elif str(tok).lower() == "select":
                # 如果标记为 "select" 关键字，则设置子查询标志
                isSubQuery = True
        return isSubQuery

    def identifyLiterals(self, tokenList):
        blankTokens = [sqlparse.tokens.Name, sqlparse.tokens.Name.Placeholder]
        blankTokenTypes = [sqlparse.sql.Identifier]

        for tok in tokenList.tokens:
            if isinstance(tok, sqlparse.sql.TokenList):
                # 如果标记是 TokenList 类型，则设置其类型为 INTERNAL，并递归调用 identifyLiterals 方法
                tok.ptype = INTERNAL
                self.identifyLiterals(tok)
            elif tok.ttype == sqlparse.tokens.Keyword or str(tok).lower() == "select":
                # 如果标记是关键字或 "select" 关键字，则设置其类型为 KEYWORD
                tok.ttype = KEYWORD
            elif tok.ttype == sqlparse.tokens.Number.Integer or tok.ttype == sqlparse.tokens.Literal.Number.Integer:
                # 如果标记是整数类型，则设置其类型为 INTEGER
                tok.ttype = INTEGER
            elif tok.ttype == sqlparse.tokens.Number.Hexadecimal or tok.ttype == sqlparse.tokens.Literal.Number.Hexadecimal:
                # 如果标记是十六进制数类型，则设置其类型为 HEX
                tok.ttype = HEX
            elif tok.ttype == sqlparse.tokens.Number.Float or tok.ttype == sqlparse.tokens.Literal.Number.Float:
                # 如果标记是浮点数类型，则设置其类型为 FLOAT
                tok.ttype = FLOAT
            elif tok.ttype == sqlparse.tokens.String.Symbol or tok.ttype == sqlparse.tokens.String.Single or tok.ttype == sqlparse.tokens.Literal.String.Single or tok.ttype == sqlparse.tokens.Literal.String.Symbol:
                # 如果标记是字符串类型，则设置其类型为 STRING
                tok.ttype = STRING
            elif tok.ttype == sqlparse.tokens.Wildcard:
                # 如果标记是通配符类型，则设置其类型为 WILDCARD
                tok.ttype = WILDCARD
            elif tok.ttype in blankTokens or isinstance(tok, blankTokenTypes[0]):
                # 如果标记是列名或占位符类型，则设置其类型为 COLUMN
                tok.ttype = COLUMN

    def identifyFunctions(self, tokenList):
        for tok in tokenList.tokens:
            if isinstance(tok, sqlparse.sql.Function):
                # 如果标记是函数类型，则设置 parseTreeSentinel 为 True
                self.parseTreeSentinel = True
            elif isinstance(tok, sqlparse.sql.Parenthesis):
                # 如果标记是括号类型，则设置 parseTreeSentinel 为 False
                self.parseTreeSentinel = False
            if self.parseTreeSentinel:
                # 如果 parseTreeSentinel 为 True，则将标记类型设置为 FUNCTION
                tok.ttype = FUNCTION
            if isinstance(tok, sqlparse.sql.TokenList):
                # 如果标记是 TokenList 类型，则递归调用 identifyFunctions 方法
                self.identifyFunctions(tok)

    def identifyTables(self, tokenList):
        if tokenList.ptype == SUBQUERY:
            # 如果标记列表类型是子查询，则在 tableStack 中添加一个 False
            self.tableStack.append(False)

        for i in range(len(tokenList.tokens)):
            prevtok = tokenList.tokens[i - 1]
            tok = tokenList.tokens[i]

            if str(tok) == "." and tok.ttype == sqlparse.tokens.Punctuation and prevtok.ttype == COLUMN:
                # 如果标记是 "." 并且前一个标记是列，则将前一个标记类型设置为 TABLE
                prevtok.ttype = TABLE

            elif str(tok).lower() == "from" and tok.ttype == sqlparse.tokens.Keyword:
                # 如果标记是 "from" 关键字，则将 tableStack 顶部设置为 True
                self.tableStack[-1] = True

            elif str(tok).lower() in ["where", "on", "group", "order",
                                      "union"] and tok.ttype == sqlparse.tokens.Keyword:
                # 如果标记是 "where", "on", "group", "order" 或 "union" 关键字，则将 tableStack 顶部设置为 False
                self.tableStack[-1] = False

            if isinstance(tok, sqlparse.sql.TokenList):
                # 如果标记是 TokenList 类型，则递归调用 identifyTables 方法
                self.identifyTables(tok)

            elif tok.ttype == COLUMN:
                # 如果标记是列，并且 tableStack 顶部为 True，则将标记类型设置为 TABLE
                if self.tableStack[-1]:
                    tok.ttype = TABLE

        if tokenList.ptype == SUBQUERY:
            # 如果标记列表类型是子查询，则从 tableStack 中移除顶部元素
            self.tableStack.pop()

    def __str__(self):
        return ' '.join([str(tok) for tok in self.tokens])

    def parseSql(self):
        return [str(tok) for tok in self.tokens]
#############################################################################

#############################################################################
#缩略词处理
def revert_abbrev(line):
    # 定义正则表达式模式
    pat_is = re.compile(r"(it|he|she|that|this|there|here)\"s", re.I)
    # 匹配 's
    pat_s1 = re.compile(r"(?<=[a-zA-Z])\"s")
    # 匹配 s
    pat_s2 = re.compile(r"(?<=s)\"s?")
    # 匹配 not
    pat_not = re.compile(r"(?<=[a-zA-Z])n\"t")
    # 匹配 would
    pat_would = re.compile(r"(?<=[a-zA-Z])\"d")
    # 匹配 will
    pat_will = re.compile(r"(?<=[a-zA-Z])\"ll")
    # 匹配 am
    pat_am = re.compile(r"(?<=[I|i])\"m")
    # 匹配 are
    pat_are = re.compile(r"(?<=[a-zA-Z])\"re")
    # 匹配 have
    pat_ve = re.compile(r"(?<=[a-zA-Z])\"ve")

    # 使用正则表达式替换缩写
    line = pat_is.sub(r"\1 is", line)
    line = pat_s1.sub("", line)
    line = pat_s2.sub("", line)
    line = pat_not.sub(" not", line)
    line = pat_would.sub(" would", line)
    line = pat_will.sub(" will", line)
    line = pat_am.sub(" am", line)
    line = pat_are.sub(" are", line)
    line = pat_ve.sub(" have", line)

    return line

#获取词性
def get_wordpos(tag):
    if tag.startswith('J'):
        return wordnet.ADJ  # 形容词
    elif tag.startswith('V'):
        return wordnet.VERB  # 动词
    elif tag.startswith('N'):
        return wordnet.NOUN  # 名词
    elif tag.startswith('R'):
        return wordnet.ADV  # 副词
    else:
        return None  # 其他情况返回 None

#---------------------子函数1：句子的去冗--------------------
def process_nl_line(line):
    # 句子预处理
    line = revert_abbrev(line)  # 还原缩写
    line = re.sub('\t+', '\t', line)  # 替换多个制表符为一个
    line = re.sub('\n+', '\n', line)  # 替换多个换行符为一个
    line = line.replace('\n', ' ')  # 替换换行符为空格
    line = line.replace('\t', ' ')  # 替换制表符为空格
    line = re.sub(' +', ' ', line)  # 替换多个空格为一个
    line = line.strip()  # 去除首尾空格

    # 骆驼命名转下划线
    line = inflection.underscore(line)

    # 去除括号里内容
    space = re.compile(r"\([^\(|^\)]+\)")  # 匹配括号内的内容
    line = re.sub(space, '', line)

    # 去除末尾.和空格
    line = line.strip()  # 去除首尾空格和句号

    return line


#---------------------子函数1：句子的分词--------------------
def process_sent_word(line):
    # 找单词
    line = re.findall(r"[\w]+|[^\s\w]", line)  # 使用正则表达式提取单词和标点符号
    line = ' '.join(line)  # 将提取的单词和标点符号用空格连接成字符串

    # 替换小数
    decimal = re.compile(r"\d+(\.\d+)+")
    line = re.sub(decimal, 'TAGINT', line)  # 将小数替换为 TAGINT
    # 替换字符串
    string = re.compile(r'\"[^\"]+\"')
    line = re.sub(string, 'TAGSTR', line)  # 将字符串替换为 TAGSTR
    # 替换十六进制
    decimal = re.compile(r"0[xX][A-Fa-f0-9]+")
    line = re.sub(decimal, 'TAGINT', line)  # 将十六进制数替换为 TAGINT
    # 替换数字
    number = re.compile(r"\s?\d+\s?")
    line = re.sub(number, ' TAGINT ', line)  # 将数字替换为 TAGINT
    # 替换字符
    other = re.compile(r"(?<![A-Z|a-z|_|])\d+[A-Za-z]+")  # 匹配数字和字母混合的字符串
    line = re.sub(other, 'TAGOER', line)  # 将匹配的字符串替换为 TAGOER

    cut_words = line.split(' ')  # 将处理后的字符串按空格分割成单词列表
    # 全部小写化
    cut_words = [x.lower() for x in cut_words]  # 将单词列表中的每个单词转换为小写

    # 词性标注
    word_tags = pos_tag(cut_words)  # 对单词列表进行词性标注
    tags_dict = dict(word_tags)  # 将词性标注结果转换为字典

    word_list = []
    for word in cut_words:
        word_pos = get_wordpos(tags_dict[word])  # 获取单词的词性
        if word_pos in ['a', 'v', 'n', 'r']:
            # 词性还原
            word = wnler.lemmatize(word, pos=word_pos)  # 使用词性还原单词
        # 词干提取 (效果最好）
        word = wordnet.morphy(word) if wordnet.morphy(word) else word  # 使用词干提取单词
        word_list.append(word)  # 将处理后的单词添加到结果列表中

    return word_list  # 返回处理后的单词列表


#############################################################################

def filter_all_invachar(line):
    # 去除非常用符号；防止解析有误
    line = re.sub('[^(0-9|a-z|A-Z|\-|_|\'|\"|\-|\(|\)|\n)]+', ' ', line)  # 替换非常用符号为空格
    # 包括\r\t也清除了
    # 中横线
    line = re.sub('-+', '-', line)  # 将连续的中横线替换为单个中横线
    # 下划线
    line = re.sub('_+', '_', line)  # 将连续的下划线替换为单个下划线
    # 去除横杠
    line = line.replace('|', ' ').replace('¦', ' ')  # 将竖线和其他特殊符号替换为空格
    return line


def filter_part_invachar(line):
    #去除非常用符号；防止解析有误
    line= re.sub('[^(0-9|a-z|A-Z|\-|#|/|_|,|\'|=|>|<|\"|\-|\\|\(|\)|\?|\.|\*|\+|\[|\]|\^|\{|\}|\n)]+',' ', line)
    #包括\r\t也清除了
    # 中横线
    line = re.sub('-+', '-', line)
    # 下划线
    line = re.sub('_+', '_', line)
    # 去除横杠
    line = line.replace('|', ' ').replace('¦', ' ')
    return line

########################主函数：代码的tokens#################################
def sqlang_code_parse(line):
    line = filter_part_invachar(line)  # 过滤非常用符号
    line = re.sub('\.+', '.', line)  # 将连续的点替换为单个点
    line = re.sub('\t+', '\t', line)  # 将连续的制表符替换为单个制表符
    line = re.sub('\n+', '\n', line)  # 将连续的换行符替换为单个换行符
    line = re.sub(' +', ' ', line)  # 将连续的空格替换为单个空格

    line = re.sub('>>+', '', line)  # 新增加: 去除连续的 >>
    line = re.sub(r"\d+(\.\d+)+", 'number', line)  # 新增加: 替换小数为 'number'

    line = line.strip('\n').strip()  # 去除首尾的换行符和空格
    line = re.findall(r"[\w]+|[^\s\w]", line)  # 使用正则表达式提取单词和标点符号
    line = ' '.join(line)  # 将提取的单词和标点符号用空格连接成字符串

    try:
        query = SqlangParser(line, regex=True)  # 使用 SqlangParser 解析 SQL 语句
        typedCode = query.parseSql()  # 解析 SQL 语句
        typedCode = typedCode[:-1]  # 去除最后一个元素

        # 骆驼命名转下划线
        typedCode = inflection.underscore(' '.join(typedCode)).split(' ')  # 转换为下划线命名并分割成单词列表

        cut_tokens = [re.sub("\s+", " ", x.strip()) for x in typedCode]  # 去除多余的空格
        # 全部小写化
        token_list = [x.lower() for x in cut_tokens]  # 将单词列表中的每个单词转换为小写
        # 列表里包含 '' 和' '
        token_list = [x.strip() for x in token_list if x.strip() != '']  # 去除空字符串和只包含空格的字符串
        # 返回列表
        return token_list
    # 存在为空的情况，词向量要进行判断
    except:
        return '-1000'  # 返回错误码
########################主函数：代码的tokens#################################


#######################主函数：句子的tokens##################################

def sqlang_query_parse(line):
    line = filter_all_invachar(line)  # 过滤非常用符号
    line = process_nl_line(line)  # 处理换行符等
    word_list = process_sent_word(line)  # 处理单词，进行词性标注和词干提取

    # 分完词后,再去掉括号
    for i in range(0, len(word_list)):
        if re.findall('[\(\)]', word_list[i]):  # 查找括号
            word_list[i] = ''  # 将包含括号的单词替换为空字符串

    # 列表里包含 '' 或 ' '
    word_list = [x.strip() for x in word_list if x.strip() != '']  # 去除空字符串和只包含空格的字符串

    # 返回解析后的单词列表
    return word_list


def sqlang_context_parse(line):
    line = filter_part_invachar(line)  # 过滤非常用符号
    line = process_nl_line(line)  # 处理换行符等
    word_list = process_sent_word(line)  # 处理单词，进行词性标注和词干提取

    # 列表里包含 '' 或 ' '
    word_list = [x.strip() for x in word_list if x.strip() != '']  # 去除空字符串和只包含空格的字符串

    # 返回解析后的单词列表
    return word_list

#######################主函数：句子的tokens##################################


if __name__ == '__main__':
    print(sqlang_code_parse('""geometry": {"type": "Polygon" , 111.676,"coordinates": [[[6.69245274714546, 51.1326962505233], [6.69242714158622, 51.1326908883821], [6.69242919794447, 51.1326955158344], [6.69244041615532, 51.1326998744549], [6.69244125953742, 51.1327001609189], [6.69245274714546, 51.1326962505233]]]} How to 123 create a (SQL  Server function) to "join" multiple rows from a subquery into a single delimited field?'))
    print(sqlang_query_parse("change row_height and column_width in libreoffice calc use python tagint"))
    print(sqlang_query_parse('MySQL Administrator Backups: "Compatibility Mode", What Exactly is this doing?'))
    print(sqlang_code_parse('>UPDATE Table1 \n SET Table1.col1 = Table2.col1 \n Table1.col2 = Table2.col2 FROM \n Table2 WHERE \n Table1.id =  Table2.id'))
    print(sqlang_code_parse("SELECT\n@supplyFee:= 0\n@demandFee := 0\n@charedFee := 0\n"))
    print(sqlang_code_parse('@prev_sn := SerialNumber,\n@prev_toner := Remain_Toner_Black\n'))
    print(sqlang_code_parse(' ;WITH QtyCTE AS (\n  SELECT  [Category] = c.category_name\n          , [RootID] = c.category_id\n          , [ChildID] = c.category_id\n  FROM    Categories c\n  UNION ALL \n  SELECT  cte.Category\n          , cte.RootID\n          , c.category_id\n  FROM    QtyCTE cte\n          INNER JOIN Categories c ON c.father_id = cte.ChildID\n)\nSELECT  cte.RootID\n        , cte.Category\n        , COUNT(s.sales_id)\nFROM    QtyCTE cte\n        INNER JOIN Sales s ON s.category_id = cte.ChildID\nGROUP BY cte.RootID, cte.Category\nORDER BY cte.RootID\n'))
    print(sqlang_code_parse("DECLARE @Table TABLE (ID INT, Code NVARCHAR(50), RequiredID INT);\n\nINSERT INTO @Table (ID, Code, RequiredID)   VALUES\n    (1, 'Physics', NULL),\n    (2, 'Advanced Physics', 1),\n    (3, 'Nuke', 2),\n    (4, 'Health', NULL);    \n\nDECLARE @DefaultSeed TABLE (ID INT, Code NVARCHAR(50), RequiredID INT);\n\nWITH hierarchy \nAS (\n    --anchor\n    SELECT  t.ID , t.Code , t.RequiredID\n    FROM @Table AS t\n    WHERE t.RequiredID IS NULL\n\n    UNION ALL   \n\n    --recursive\n    SELECT  t.ID \n          , t.Code \n          , h.ID        \n    FROM hierarchy AS h\n        JOIN @Table AS t \n            ON t.RequiredID = h.ID\n    )\n\nINSERT INTO @DefaultSeed (ID, Code, RequiredID)\nSELECT  ID \n        , Code \n        , RequiredID\nFROM hierarchy\nOPTION (MAXRECURSION 10)\n\n\nDECLARE @NewSeed TABLE (ID INT IDENTITY(10, 1), Code NVARCHAR(50), RequiredID INT)\n\nDeclare @MapIds Table (aOldID int,aNewID int)\n\n;MERGE INTO @NewSeed AS TargetTable\nUsing @DefaultSeed as Source on 1=0\nWHEN NOT MATCHED then\n Insert (Code,RequiredID)\n Values\n (Source.Code,Source.RequiredID)\nOUTPUT Source.ID ,inserted.ID into @MapIds;\n\n\nUpdate @NewSeed Set RequiredID=aNewID\nfrom @MapIds\nWhere RequiredID=aOldID\n\n\n/*\n--@NewSeed should read like the following...\n[ID]  [Code]           [RequiredID]\n10....Physics..........NULL\n11....Health...........NULL\n12....AdvancedPhysics..10\n13....Nuke.............12\n*/\n\nSELECT *\nFROM @NewSeed\n"))



