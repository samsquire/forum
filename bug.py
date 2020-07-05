import multiprocessing
import time

def task1(arg1):
    time.sleep(5)
    return "RESULT1"

def task2(arg1):
    time.sleep(5)
    return "RESULT2"

def task3(arg3):
    time.sleep(5)
    return "RESULT3"

def worker(q, r):
    running = True
    while running:
        work, args = q.get()
        print("Received " + work)
        if work == None:
            running = False
            continue
        result = globals()[work](*args)
        print("Done " + work)
        r.put(result)


queue1 = multiprocessing.Queue()
queue2 = multiprocessing.Queue()
queue3 = multiprocessing.Queue()

r1 = multiprocessing.Queue()
r2 = multiprocessing.Queue()
r3 = multiprocessing.Queue()

p1 = multiprocessing.Process(target=worker, args=(queue1, r1))
p1.daemon = True
p2 = multiprocessing.Process(target=worker, args=(queue2, r2))
p2.daemon = True
p3 = multiprocessing.Process(target=worker, args=(queue3, r3))
p3.daemon = True

p1.start()
p2.start()
p3.start()

queue1.put(("task1", (0,)))
queue2.put(("task2", (0,)))
queue3.put(("task3", (0,)))

print(r1.get())
print(r2.get())
print(r3.get())
