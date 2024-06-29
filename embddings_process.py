import pickle
import numpy as np
from gensim.models import KeyedVectors

# 将词向量文件保存为二进制文件
def trans_bin(path1, path2):
    # 加载词向量
    wv_from_text = KeyedVectors.load_word2vec_format(path1, binary=False)
    # 保存词向量为二进制文件，加快加载速度
    wv_from_text.init_sims(replace=True)
    wv_from_text.save(path2)

# 构建新的词典和词向量矩阵
def get_new_dict(type_vec_path, type_word_path, final_vec_path, final_word_path):
    # 加载词向量文件
    model = KeyedVectors.load(type_vec_path, mmap='r')

    with open(type_word_path, 'r') as f:
        total_word = eval(f.read())

    # 初始化词典和词向量矩阵
    word_dict = ['PAD', 'SOS', 'EOS', 'UNK']
    fail_word = []
    rng = np.random.RandomState(None)
    pad_embedding = np.zeros(shape=(1, 300)).squeeze()
    unk_embedding = rng.uniform(-0.25, 0.25, size=(1, 300)).squeeze()
    sos_embedding = rng.uniform(-0.25, 0.25, size=(1, 300)).squeeze()
    eos_embedding = rng.uniform(-0.25, 0.25, size=(1, 300)).squeeze()
    word_vectors = [pad_embedding, sos_embedding, eos_embedding, unk_embedding]

    # 根据词典，获取每个词的词向量
    for word in total_word:
        try:
            word_vectors.append(model.wv[word])
            word_dict.append(word)
        except:
            fail_word.append(word)

    word_vectors = np.array(word_vectors)
    word_dict = dict(map(reversed, enumerate(word_dict)))

    # 保存词向量和词典
    with open(final_vec_path, 'wb') as file:
        pickle.dump(word_vectors, file)

    with open(final_word_path, 'wb') as file:
        pickle.dump(word_dict, file)

    print("完成")

# 得到词在词典中的位置
def get_index(type, text, word_dict):
    location = []
    if type == 'code':
        location.append(1)
        len_c = len(text)
        if len_c + 1 < 350:
            if len_c == 1 and text[0] == '-1000':
                location.append(2)
            else:
                for i in range(0, len_c):
                    index = word_dict.get(text[i], word_dict['UNK'])
                    location.append(index)
                location.append(2)
        else:
            for i in range(0, 348):
                index = word_dict.get(text[i], word_dict['UNK'])
                location.append(index)
            location.append(2)
    else:
        if len(text) == 0:
            location.append(0)
        elif text[0] == '-10000':
            location.append(0)
        else:
            for i in range(0, len(text)):
                index = word_dict.get(text[i], word_dict['UNK'])
                location.append(index)

    return location

# 将训练、测试、验证语料序列化
# 查询：25 上下文：100 代码：350
def serialization(word_dict_path, type_path, final_type_path):
    with open(word_dict_path, 'rb') as f:
        word_dict = pickle.load(f)

    with open(type_path, 'r') as f:
        corpus = eval(f.read())

    total_data = []

    for i in range(len(corpus)):
        qid = corpus[i][0]

        Si_word_list = get_index('text', corpus[i][1][0], word_dict)
        Si1_word_list = get_index('text', corpus[i][1][1], word_dict)
        tokenized_code = get_index('code', corpus[i][2][0], word_dict)
        query_word_list = get_index('text', corpus[i][3], word_dict)
        block_length = 4
        label = 0

        Si_word_list = Si_word_list[:100] if len(Si_word_list) > 100 else Si_word_list + [0] * (100 - len(Si_word_list))
        Si1_word_list = Si1_word_list[:100] if len(Si1_word_list) > 100 else Si1_word_list + [0] * (100 - len(Si1_word_list))
        tokenized_code = tokenized_code[:350] + [0] * (350 - len(tokenized_code))
        query_word_list = query_word_list[:25] if len(query_word_list) > 25 else query_word_list + [0] * (
                    25 - len(query_word_list))

        total_data.append([qid, Si_word_list, Si1_word_list, tokenized_code, query_word_list, block_length, label])

    with open(final_type_path, 'wb') as f:
        pickle.dump(total_data, f)

    # 主函数，定义词向量文件、词典文件、语料文件的路径，并调用上述函数进行处理
if __name__ == '__main__':
    # 词向量文件路径
    ps_path_bin = '../hnn_process/embeddings/10_10/python_struc2vec.bin'
    sql_path_bin = '../hnn_process/embeddings/10_8_embeddings/sql_struc2vec.bin'

    # ==========================最初基于Staqc的词典和词向量==========================

    python_word_path = '../hnn_process/data/word_dict/python_word_vocab_dict.txt'
    python_word_vec_path = '../hnn_process/embeddings/python/python_word_vocab_final.pkl'
    python_word_dict_path = '../hnn_process/embeddings/python/python_word_dict_final.pkl'

    sql_word_path = '../hnn_process/data/word_dict/sql_word_vocab_dict.txt'
    sql_word_vec_path = '../hnn_process/embeddings/sql/sql_word_vocab_final.pkl'
    sql_word_dict_path = '../hnn_process/embeddings/sql/sql_word_dict_final.pkl'

    # get_new_dict(ps_path_bin, python_word_path, python_word_vec_path, python_word_dict_path)
    # get_new_dict(sql_path_bin, sql_word_path, sql_word_vec_path, sql_word_dict_path)

    # =======================================最后打标签的语料========================================

    # sql 待处理语料地址
    new_sql_staqc = '../hnn_process/ulabel_data/staqc/sql_staqc_unlabled_data.txt'
    new_sql_large = '../hnn_process/ulabel_data/large_corpus/multiple/sql_large_multiple_unlable.txt'
    large_word_dict_sql = '../hnn_process/ulabel_data/sql_word_dict.txt'

    # sql最后的词典和对应的词向量
    sql_final_word_vec_path = '../hnn_process/ulabel_data/large_corpus/sql_word_vocab_final.pkl'
    sqlfinal_word_dict_path = '../hnn_process/ulabel_data/large_corpus/sql_word_dict_final.pkl'

    # get_new_dict(sql_path_bin, final_word_dict_sql, sql_final_word_vec_path, sql_final_word_dict_path)
    # get_new_dict_append(sql_path_bin, sql_word_dict_path, sql_word_vec_path, large_word_dict_sql, sql_final_word_vec_path,sql_final_word_dict_path)

    staqc_sql_f = '../hnn_process/ulabel_data/staqc/seri_sql_staqc_unlabled_data.pkl'
    large_sql_f = '../hnn_process/ulabel_data/large_corpus/multiple/seri_ql_large_multiple_unlable.pkl'
    # Serialization(sql_final_word_dict_path, new_sql_staqc, staqc_sql_f)
    # Serialization(sql_final_word_dict_path, new_sql_large, large_sql_f)

    # python
    new_python_staqc = '../hnn_process/ulabel_data/staqc/python_staqc_unlabled_data.txt'
    new_python_large = '../hnn_process/ulabel_data/large_corpus/multiple/python_large_multiple_unlable.txt'
    final_word_dict_python = '../hnn_process/ulabel_data/python_word_dict.txt'
    large_word_dict_python = '../hnn_process/ulabel_data/python_word_dict.txt'

    # python最后的词典和对应的词向量
    python_final_word_vec_path = '../hnn_process/ulabel_data/large_corpus/python_word_vocab_final.pkl'
    python_final_word_dict_path = '../hnn_process/ulabel_data/large_corpus/python_word_dict_final.pkl'

    # get_new_dict(ps_path_bin, final_word_dict_python, python_final_word_vec_path, python_final_word_dict_path)
    # get_new_dict_append(ps_path_bin, python_word_dict_path, python_word_vec_path, large_word_dict_python, python_final_word_vec_path,python_final_word_dict_path)

    # 处理成打标签的形式
    staqc_python_f = '../hnn_process/ulabel_data/staqc/seri_python_staqc_unlabled_data.pkl'
    large_python_f = '../hnn_process/ulabel_data/large_corpus/multiple/seri_python_large_multiple_unlable.pkl'
    # Serialization(python_final_word_dict_path, new_python_staqc, staqc_python_f)
    serialization(python_final_word_dict_path, new_python_large, large_python_f)

    print('序列化完毕')
    # test2(test_python1,test_python2,python_final_word_dict_path,python_final_word_vec_path)
