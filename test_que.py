from myfinance.que_control import Que_Temp, Que_element


que = Que_Temp()
q1 = Que_element(1, ['002841'])
que.add_que_class(q1)
code_list = ['198f9h3', '12f34g34', '1f34fg34gf', '34f34ff']
que.gen_from_code_list(code_list)
