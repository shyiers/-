# -*- coding: utf-8 -*-
import re
import ast
import sys
import token
import tokenize

from nltk import wordpunct_tokenize
from io import StringIO
# 骆驼命名法
import inflection

# 词性还原
from nltk import pos_tag
from nltk.stem import WordNetLemmatizer

wnler = WordNetLemmatizer()

# 词干提取
from nltk.corpus import wordnet

#############################################################################

PATTERN_VAR_EQUAL = re.compile("(\s*[_a-zA-Z][_a-zA-Z0-9]*\s*)(,\s*[_a-zA-Z][_a-zA-Z0-9]*\s*)*=")
PATTERN_VAR_FOR = re.compile("for\s+[_a-zA-Z][_a-zA-Z0-9]*\s*(,\s*[_a-zA-Z][_a-zA-Z0-9]*)*\s+in")


def repair_program_io(code):
    # 定义正则表达式模式用于匹配特定的输入和输出格式
    pattern_case1_in = re.compile("In ?\[\d+]: ?")  # 匹配 "In[数字]: " 格式
    pattern_case1_out = re.compile("Out ?\[\d+]: ?")  # 匹配 "Out[数字]: " 格式
    pattern_case1_cont = re.compile("( )+\.+: ?")  # 匹配 "(空格)...: " 格式

    pattern_case2_in = re.compile(">>> ?")  # 匹配 ">>> " 格式
    pattern_case2_cont = re.compile("\.\.\. ?")  # 匹配 "... " 格式

    patterns = [pattern_case1_in, pattern_case1_out, pattern_case1_cont, pattern_case2_in, pattern_case2_cont]

    # 将代码按行分割
    lines = code.split("\n")
    # 初始化行标志数组，默认值为0
    lines_flags = [0 for _ in range(len(lines))]

    code_list = []  # 用于存储修复后的代码块

    # 匹配模式并标记行
    for line_idx in range(len(lines)):
        line = lines[line_idx]
        for pattern_idx in range(len(patterns)):
            if re.match(patterns[pattern_idx], line):
                lines_flags[line_idx] = pattern_idx + 1
                break
    lines_flags_string = "".join(map(str, lines_flags))

    bool_repaired = False

    # 修复代码
    if lines_flags.count(0) == len(lines_flags):  # 如果没有匹配到任何模式，不需要修复
        repaired_code = code
        code_list = [code]
        bool_repaired = True

    elif re.match(re.compile("(0*1+3*2*0*)+"), lines_flags_string) or \
            re.match(re.compile("(0*4+5*0*)+"), lines_flags_string):
        repaired_code = ""
        pre_idx = 0
        sub_block = ""
        if lines_flags[0] == 0:
            flag = 0
            while (flag == 0):
                repaired_code += lines[pre_idx] + "\n"
                pre_idx += 1
                flag = lines_flags[pre_idx]
            sub_block = repaired_code
            code_list.append(sub_block.strip())
            sub_block = ""  # 清空子块

        for idx in range(pre_idx, len(lines_flags)):
            if lines_flags[idx] != 0:
                repaired_code += re.sub(patterns[lines_flags[idx] - 1], "", lines[idx]) + "\n"

                # 清空子块记录
                if len(sub_block.strip()) and (idx > 0 and lines_flags[idx - 1] == 0):
                    code_list.append(sub_block.strip())
                    sub_block = ""
                sub_block += re.sub(patterns[lines_flags[idx] - 1], "", lines[idx]) + "\n"

            else:
                if len(sub_block.strip()) and (idx > 0 and lines_flags[idx - 1] != 0):
                    code_list.append(sub_block.strip())
                    sub_block = ""
                sub_block += lines[idx] + "\n"

        # 避免遗漏最后一个单元
        if len(sub_block.strip()):
            code_list.append(sub_block.strip())

        if len(repaired_code.strip()) != 0:
            bool_repaired = True

    if not bool_repaired:  # 如果不是典型情况，则仅删除每个 Out 之后的 0 标志行
        repaired_code = ""
        sub_block = ""
        bool_after_Out = False
        for idx in range(len(lines_flags)):
            if lines_flags[idx] != 0:
                if lines_flags[idx] == 2:
                    bool_after_Out = True
                else:
                    bool_after_Out = False
                repaired_code += re.sub(patterns[lines_flags[idx] - 1], "", lines[idx]) + "\n"

                if len(sub_block.strip()) and (idx > 0 and lines_flags[idx - 1] == 0):
                    code_list.append(sub_block.strip())
                    sub_block = ""
                sub_block += re.sub(patterns[lines_flags[idx] - 1], "", lines[idx]) + "\n"

            else:
                if not bool_after_Out:
                    repaired_code += lines[idx] + "\n"

                if len(sub_block.strip()) and (idx > 0 and lines_flags[idx - 1] != 0):
                    code_list.append(sub_block.strip())
                    sub_block = ""
                sub_block += lines[idx] + "\n"

    return repaired_code, code_list


def get_vars(ast_root):
    # 遍历抽象语法树 (AST) 并收集所有变量名
    return sorted(
        {node.id for node in ast.walk(ast_root) if isinstance(node, ast.Name) and not isinstance(node.ctx, ast.Load)}
    )


def get_vars_heuristics(code):
    varnames = set()  # 用于存储变量名的集合
    code_lines = [_ for _ in code.split("\n") if len(_.strip())]  # 按行拆分代码并去除空行

    # 尽力解析代码
    start = 0
    end = len(code_lines) - 1
    bool_success = False
    while not bool_success:
        try:
            root = ast.parse("\n".join(code_lines[start:end]))  # 尝试解析代码
        except:
            end -= 1  # 如果解析失败，缩短解析范围
        else:
            bool_success = True  # 解析成功
    # print("Best effort parse at: start = %d and end = %d." % (start, end))
    varnames = varnames.union(set(get_vars(root)))  # 提取变量名并加入集合
    # print("Var names from base effort parsing: %s." % str(varnames))

    # 处理剩余的代码行
    for line in code_lines[end:]:
        line = line.strip()
        try:
            root = ast.parse(line)  # 尝试解析单行代码
        except:
            # 匹配变量赋值模式
            pattern_var_equal_matched = re.match(PATTERN_VAR_EQUAL, line)
            if pattern_var_equal_matched:
                match = pattern_var_equal_matched.group()[:-1]  # 去掉 "="
                varnames = varnames.union(set([_.strip() for _ in match.split(",")]))  # 提取变量名并加入集合

            # 匹配for循环中的变量模式
            pattern_var_for_matched = re.search(PATTERN_VAR_FOR, line)
            if pattern_var_for_matched:
                match = pattern_var_for_matched.group()[3:-2]  # 去掉 "for" 和 "in"
                varnames = varnames.union(set([_.strip() for _ in match.split(",")]))  # 提取变量名并加入集合

        else:
            varnames = varnames.union(get_vars(root))  # 提取变量名并加入集合

    return varnames  # 返回变量名集合

def PythonParser(code):
    bool_failed_var = False  # 标记变量解析是否失败
    bool_failed_token = False  # 标记代码标记解析是否失败

    try:
        root = ast.parse(code)  # 尝试解析代码为 AST
        varnames = set(get_vars(root))  # 提取变量名
    except:
        repaired_code, _ = repair_program_io(code)  # 尝试修复代码
        try:
            root = ast.parse(repaired_code)  # 尝试解析修复后的代码
            varnames = set(get_vars(root))  # 提取变量名
        except:
            bool_failed_var = True  # 标记变量解析失败
            varnames = get_vars_heuristics(code)  # 使用启发式方法提取变量名

    tokenized_code = []  # 初始化代码标记列表

    def first_trial(_code):
        if len(_code) == 0:
            return True  # 如果代码为空，返回 True
        try:
            g = tokenize.generate_tokens(StringIO(_code).readline)
            term = next(g)  # 尝试生成第一个标记
        except:
            return False  # 如果生成标记失败，返回 False
        else:
            return True  # 成功生成标记，返回 True

    bool_first_success = first_trial(code)
    while not bool_first_success:
        code = code[1:]  # 去掉代码的第一个字符
        bool_first_success = first_trial(code)  # 重新尝试生成标记
    g = tokenize.generate_tokens(StringIO(code).readline)
    term = next(g)  # 获取第一个标记

    bool_finished = False
    while not bool_finished:
        term_type = term[0]  # 获取标记类型
        lineno = term[2][0] - 1  # 获取标记所在行
        posno = term[3][1] - 1  # 获取标记所在列
        if token.tok_name[term_type] in {"NUMBER", "STRING", "NEWLINE"}:
            tokenized_code.append(token.tok_name[term_type])  # 直接添加标记类型
        elif not token.tok_name[term_type] in {"COMMENT", "ENDMARKER"} and len(term[1].strip()):
            candidate = term[1].strip()
            if candidate not in varnames:
                tokenized_code.append(candidate)  # 添加标记内容
            else:
                tokenized_code.append("VAR")  # 添加变量标记

        # 获取下一个标记
        bool_success_next = False
        while not bool_success_next:
            try:
                term = next(g)  # 尝试获取下一个标记
            except StopIteration:
                bool_finished = True  # 结束标记生成
                break
            except:
                bool_failed_token = True  # 标记代码标记解析失败
                code_lines = code.split("\n")
                if lineno > len(code_lines) - 1:
                    print(sys.exc_info())  # 输出错误信息
                else:
                    failed_code_line = code_lines[lineno]  # 获取错误行
                    if posno < len(failed_code_line) - 1:
                        failed_code_line = failed_code_line[posno:]
                        tokenized_failed_code_line = wordpunct_tokenize(failed_code_line)  # 标记化错误行片段
                        tokenized_code += tokenized_failed_code_line  # 添加到之前的标记输出
                    if lineno < len(code_lines) - 1:
                        code = "\n".join(code_lines[lineno + 1:])
                        g = tokenize.generate_tokens(StringIO(code).readline)  # 重新生成标记
                    else:
                        bool_finished = True
                        break
            else:
                bool_success_next = True

    return tokenized_code, bool_failed_var, bool_failed_token  # 返回标记化代码、变量解析失败标记和代码标记解析失败标记


#############################################################################

#############################################################################
# 缩略词处理
def revert_abbrev(line):
    # 定义正则表达式模式
    pat_is = re.compile(r"(it|he|she|that|this|there|here)('s)", re.I)
    # 匹配 's
    pat_s1 = re.compile(r"(?<=[a-zA-Z])'s")
    # 匹配 s
    pat_s2 = re.compile(r"(?<=s)'s?")
    # 匹配 not
    pat_not = re.compile(r"(?<=[a-zA-Z])n't")
    # 匹配 would
    pat_would = re.compile(r"(?<=[a-zA-Z])'d")
    # 匹配 will
    pat_will = re.compile(r"(?<=[a-zA-Z])'ll")
    # 匹配 am
    pat_am = re.compile(r"(?<=[I|i])'m")
    # 匹配 are
    pat_are = re.compile(r"(?<=[a-zA-Z])'re")
    # 匹配 have
    pat_ve = re.compile(r"(?<=[a-zA-Z])'ve")

    # 替换缩写形式
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
        return None  # 未知词性


# ---------------------子函数1：句子的去冗--------------------
def process_nl_line(line):
    # 句子预处理
    line = revert_abbrev(line)  # 将缩写还原为完整形式
    line = re.sub('\t+', '\t', line)  # 将多个制表符替换为单个制表符
    line = re.sub('\n+', '\n', line)  # 将多个换行符替换为单个换行符
    line = line.replace('\n', ' ')  # 将换行符替换为空格
    line = re.sub(' +', ' ', line)  # 将多个空格替换为单个空格
    line = line.strip()  # 去除字符串开头和结尾的空格

    # 骆驼命名转下划线
    line = inflection.underscore(line)

    # 去除括号里内容
    space = re.compile(r"\([^(|^)]+\)")  # 匹配括号及其内容
    line = re.sub(space, '', line)  # 去除括号及其内容

    # 去除开始和末尾空格
    line = line.strip()

    return line


# ---------------------子函数1：句子的分词--------------------
def process_sent_word(line):

    # 找单词
    line = re.findall(r"\w+|[^\s\w]", line)
    line = ' '.join(line)

    # 替换小数
    decimal = re.compile(r"\d+(\.\d+)+")
    line = re.sub(decimal, 'TAGINT', line)

    # 替换字符串
    string = re.compile(r'\"[^\"]+\"')
    line = re.sub(string, 'TAGSTR', line)

    # 替换十六进制
    hex_decimal = re.compile(r"0[xX][A-Fa-f0-9]+")
    line = re.sub(hex_decimal, 'TAGINT', line)

    # 替换数字
    number = re.compile(r"\s?\d+\s?")
    line = re.sub(number, ' TAGINT ', line)

    # 替换字符
    other = re.compile(r"(?<![A-Z|a-z_])\d+[A-Za-z]+")
    line = re.sub(other, 'TAGOER', line)

    # 分割单词
    cut_words = line.split(' ')

    # 全部小写化
    cut_words = [x.lower() for x in cut_words]

    # 词性标注
    word_tags = pos_tag(cut_words)
    tags_dict = dict(word_tags)

    word_list = []
    for word in cut_words:
        word_pos = get_wordpos(tags_dict[word])
        if word_pos in ['a', 'v', 'n', 'r']:
            # 词性还原
            word = wnler.lemmatize(word, pos=word_pos)

        # 词干提取(效果最好）
        word = wordnet.morphy(word) if wordnet.morphy(word) else word
        word_list.append(word)

    return word_list


#############################################################################

def filter_all_invachar(line):
    # 确保输入是一个对象
    assert isinstance(line, object)

    # 去除非常用符号，保留数字、字母、下划线、横杠、单引号、双引号和换行符
    line = re.sub('[^(0-9|a-zA-Z\-_\'\")\n]+', ' ', line)

    # 将多个连续的横杠替换为单个横杠
    line = re.sub('-+', '-', line)

    # 将多个连续的下划线替换为单个下划线
    line = re.sub('_+', '_', line)

    # 去除竖线和分隔符
    line = line.replace('|', ' ').replace('¦', ' ')

    return line


def filter_part_invachar(line):
    # 去除非常用符号，保留数字、字母、下划线、横杠、单引号、双引号和换行符
    line = re.sub('[^(0-9|a-zA-Z\-_\'\")\n]+', ' ', line)

    # 将多个连续的横杠替换为单个横杠
    line = re.sub('-+', '-', line)

    # 将多个连续的下划线替换为单个下划线
    line = re.sub('_+', '_', line)

    # 去除竖线和分隔符
    line = line.replace('|', ' ').replace('¦', ' ')

    return line

########################主函数：代码的tokens#################################
def python_code_parse(line):
    # 使用 filter_part_invachar 函数去除非常用符号
    line = filter_part_invachar(line)

    # 将多个连续的点替换为单个点
    line = re.sub('\.+', '.', line)

    # 将多个连续的制表符替换为单个制表符
    line = re.sub('\t+', '\t', line)

    # 将多个连续的换行符替换为单个换行符
    line = re.sub('\n+', '\n', line)

    # 移除 '>>' 符号
    line = re.sub('>>+', '', line)

    # 将多个连续的空格替换为单个空格
    line = re.sub(' +', ' ', line)

    # 去除字符串首尾的换行符和空格
    line = line.strip('\n').strip()

    # 使用正则表达式找到所有单词和标点符号
    line = re.findall(r"[\w]+|[^\s\w]", line)
    line = ' '.join(line)

    '''
    旧的处理逻辑被注释掉了
    line = filter_part_invachar(line)
    line = re.sub('\t+', '\t', line)
    line = re.sub('\n+', '\n', line)
    line = re.sub(' +', ' ', line)
    line = line.strip('\n').strip()
    '''
    try:
        # 使用 PythonParser 解析代码
        typedCode, failed_var, failed_token = PythonParser(line)

        # 将骆驼命名转换为下划线命名
        typedCode = inflection.underscore(' '.join(typedCode)).split(' ')

        # 去除多余的空格
        cut_tokens = [re.sub("\s+", " ", x.strip()) for x in typedCode]

        # 全部小写化
        token_list = [x.lower() for x in cut_tokens]

        # 去除列表中的空字符串
        token_list = [x.strip() for x in token_list if x.strip() != '']

        return token_list
    except:
        # 如果解析失败，返回 '-1000'
        return '-1000'


########################主函数：代码的tokens#################################


#######################主函数：句子的tokens##################################

def python_query_parse(line):
    # 使用 filter_all_invachar 去除非常用符号
    line = filter_all_invachar(line)

    # 处理换行符和制表符等
    line = process_nl_line(line)

    # 对字符串进行分词处理
    word_list = process_sent_word(line)

    # 去除单词列表中的括号
    for i in range(0, len(word_list)):
        if re.findall('[()]', word_list[i]):
            word_list[i] = ''

    # 去除列表中的空字符串和仅包含空格的字符串
    word_list = [x.strip() for x in word_list if x.strip() != '']

    return word_list


def python_context_parse(line):
    # 使用 filter_part_invachar 去除非常用符号
    line = filter_part_invachar(line)

    # 处理换行符和制表符等，并将驼峰命名转换为下划线命名
    line = process_nl_line(line)

    # 打印处理后的字符串（用于调试）
    print(line)

    # 对字符串进行分词处理
    word_list = process_sent_word(line)

    # 去除列表中的空字符串和仅包含空格的字符串
    word_list = [x.strip() for x in word_list if x.strip() != '']

    return word_list


#######################主函数：句子的tokens##################################

if __name__ == '__main__':
    print(python_query_parse("change row_height and column_width in libreoffice calc use python tagint"))
    print(python_query_parse('What is the standard way to add N seconds to datetime.time in Python?'))
    print(python_query_parse("Convert INT to VARCHAR SQL 11?"))
    print(python_query_parse(
        'python construct a dictionary {0: [0, 0, 0], 1: [0, 0, 1], 2: [0, 0, 2], 3: [0, 0, 3], ...,999: [9, 9, 9]}'))

    print(python_context_parse(
        'How to calculateAnd the value of the sum of squares defined as \n 1^2 + 2^2 + 3^2 + ... +n2 until a user specified sum has been reached sql()'))
    print(python_context_parse('how do i display records (containing specific) information in sql() 11?'))
    print(python_context_parse('Convert INT to VARCHAR SQL 11?'))

    print(python_code_parse(
        'if(dr.HasRows)\n{\n // ....\n}\nelse\n{\n MessageBox.Show("ReservationAnd Number Does Not Exist","Error", MessageBoxButtons.OK, MessageBoxIcon.Asterisk);\n}'))
    print(python_code_parse('root -> 0.0 \n while root_ * root < n: \n root = root + 1 \n print(root * root)'))
    print(python_code_parse('root = 0.0 \n while root * root < n: \n print(root * root) \n root = root + 1'))
    print(python_code_parse('n = 1 \n while n <= 100: \n n = n + 1 \n if n > 10: \n  break print(n)'))
    print(python_code_parse(
        "diayong(2) def sina_download(url, output_dir='.', merge=True, info_only=False, **kwargs):\n    if 'news.sina.com.cn/zxt' in url:\n        sina_zxt(url, output_dir=output_dir, merge=merge, info_only=info_only, **kwargs)\n  return\n\n    vid = match1(url, r'vid=(\\d+)')\n    if vid is None:\n        video_page = get_content(url)\n        vid = hd_vid = match1(video_page, r'hd_vid\\s*:\\s*\\'([^\\']+)\\'')\n  if hd_vid == '0':\n            vids = match1(video_page, r'[^\\w]vid\\s*:\\s*\\'([^\\']+)\\'').split('|')\n            vid = vids[-1]\n\n    if vid is None:\n        vid = match1(video_page, r'vid:\"?(\\d+)\"?')\n    if vid:\n   sina_download_by_vid(vid, output_dir=output_dir, merge=merge, info_only=info_only)\n    else:\n        vkey = match1(video_page, r'vkey\\s*:\\s*\"([^\"]+)\"')\n        if vkey is None:\n            vid = match1(url, r'#(\\d+)')\n            sina_download_by_vid(vid, output_dir=output_dir, merge=merge, info_only=info_only)\n            return\n        title = match1(video_page, r'title\\s*:\\s*\"([^\"]+)\"')\n        sina_download_by_vkey(vkey, title=title, output_dir=output_dir, merge=merge, info_only=info_only)"))

    print(python_code_parse("d = {'x': 1, 'y': 2, 'z': 3} \n for key in d: \n  print (key, 'corresponds to', d[key])"))
    print(python_code_parse(
        '  #       page  hour  count\n # 0     3727441     1   2003\n # 1     3727441     2    654\n # 2     3727441     3   5434\n # 3     3727458     1    326\n # 4     3727458     2   2348\n # 5     3727458     3   4040\n # 6   3727458_1     4    374\n # 7   3727458_1     5   2917\n # 8   3727458_1     6   3937\n # 9     3735634     1   1957\n # 10    3735634     2   2398\n # 11    3735634     3   2812\n # 12    3768433     1    499\n # 13    3768433     2   4924\n # 14    3768433     3   5460\n # 15  3768433_1     4   1710\n # 16  3768433_1     5   3877\n # 17  3768433_1     6   1912\n # 18  3768433_2     7   1367\n # 19  3768433_2     8   1626\n # 20  3768433_2     9   4750\n'))
