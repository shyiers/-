import pickle


def get_vocab(corpus1, corpus2):
    word_vocab = set()  # 创建一个空的集合来存储词汇表
    for corpus in [corpus1, corpus2]:  # 遍历两个语料库
        for i in range(len(corpus)):  # 遍历每个语料库中的每个元素
            word_vocab.update(corpus[i][1][0])  # 更新词汇表，加入 corpus[i][1][0] 中的单词
            word_vocab.update(corpus[i][1][1])  # 更新词汇表，加入 corpus[i][1][1] 中的单词
            word_vocab.update(corpus[i][2][0])  # 更新词汇表，加入 corpus[i][2][0] 中的单词
            word_vocab.update(corpus[i][3])  # 更新词汇表，加入 corpus[i][3] 中的单词
    print(len(word_vocab))  # 打印词汇表的长度
    return word_vocab  # 返回词汇表


def load_pickle(filename):
    with open(filename, 'rb') as f:  # 以二进制读模式打开文件
        data = pickle.load(f)  # 使用 pickle.load 读取数据
    return data  # 返回读取的数据


def vocab_processing(filepath1, filepath2, save_path):
    # 从文件读取数据并转换为集合
    with open(filepath1, 'r') as f:
        total_data1 = set(eval(f.read()))  # 将文件内容转换为集合

    with open(filepath2, 'r') as f:
        total_data2 = eval(f.read())  # 将文件内容转换为原始数据类型

    # 获取词汇表
    word_set = get_vocab(total_data2, total_data2)

    # 排除在 total_data1 中的单词
    excluded_words = total_data1.intersection(word_set)
    word_set = word_set - excluded_words

    # 打印集合的长度
    print(len(total_data1))
    print(len(word_set))

    # 将结果写入文件
    with open(save_path, 'w') as f:
        f.write(str(word_set))


if __name__ == "__main__":
    python_hnn = './data/python_hnn_data_teacher.txt'
    python_staqc = './data/staqc/python_staqc_data.txt'
    python_word_dict = './data/word_dict/python_word_vocab_dict.txt'

    sql_hnn = './data/sql_hnn_data_teacher.txt'
    sql_staqc = './data/staqc/sql_staqc_data.txt'
    sql_word_dict = './data/word_dict/sql_word_vocab_dict.txt'

    new_sql_staqc = './ulabel_data/staqc/sql_staqc_unlabled_data.txt'
    new_sql_large = './ulabel_data/large_corpus/multiple/sql_large_multiple_unlable.txt'
    large_word_dict_sql = './ulabel_data/sql_word_dict.txt'

    final_vocab_processing(sql_word_dict, new_sql_large, large_word_dict_sql)
