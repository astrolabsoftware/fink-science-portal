import yaml

def convert_hbase_string(s: str) -> (str, dict):
    """
    """
    if s == '':
        return None, None
    # split each line
    #b = s.split('\n')[0]

    # keep only the
    rowkey = s.split(' = ')[0]

    properties_string = s.split(' = ')[1]

    # this dictionary has formating issues
    fake_dic = yaml.load(
        properties_string.replace("'", "\""),
        Loader=yaml.FullLoader
    )

    # Proper dictionary. Beware, all values are string...
    dic = {i.split('=')[0]: i.split('=')[1] for i in fake_dic.keys()}

    return rowkey, dic
