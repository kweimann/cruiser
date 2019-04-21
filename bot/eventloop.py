import asyncio
import dataclasses
import heapq
import logging
import threading
import time
import typing
import uuid


@dataclasses.dataclass
class Event:
    id: str
    time: float
    priority: int
    data: typing.Any
    period: callable = None
    def __eq__(s, o): return (s.time, s.priority) == (o.time, o.priority)
    def __lt__(s, o): return (s.time, s.priority) <  (o.time, o.priority)
    def __le__(s, o): return (s.time, s.priority) <= (o.time, o.priority)
    def __gt__(s, o): return (s.time, s.priority) >  (o.time, o.priority)
    def __ge__(s, o): return (s.time, s.priority) >= (o.time, o.priority)


class Scheduler:
    def __init__(self):
        self._event_q = []
        self._lock = threading.RLock()

    def pushabs(self, abstime, priority, data, period=None):
        """
        push event into queue that will be consumed at an absolute time
        :param abstime: absolute time
        :param priority: priority
        :param data: event data
        :param period: periodically reschedule event after a period
        :return: event id
        """
        if period and not callable(period):
            _period = period
            def period(): return _period
        event_id = uuid.uuid4().hex
        event = Event(event_id, abstime, priority, data, period)
        self._push(event)
        return event_id

    def push(self, delay, priority, data, period=False):
        """
        push event into queue that will be consumed after a delay
        :param delay: delay
        :param priority: priority
        :param data: event data
        :param period: periodically reschedule event after a period
        :return: event id
        """
        abstime = time.time() + delay
        return self.pushabs(abstime, priority, data, period)

    def cancel(self, event_id):
        """
        remove item from the queue
        :param event_id: event id
        """
        with self._lock:
            self._event_q = [e for e in self._event_q if e.id != event_id]
            heapq.heapify(self._event_q)

    async def main_loop(self, consume_event, sleep_delay=0.01):
        """
        start the main loop
        :param consume_event: function that accepts event data
        :param sleep_delay: delay between two consecutive event queue checks
        """
        while True:
            event = self._pop()
            if event:
                if event.period:
                    event.time = time.time() + event.period()
                    self._push(event)
                try:
                    consume_event(event.data)
                except:
                    logging.exception("Exception thrown in the main loop")
            else:
                await asyncio.sleep(sleep_delay)

    def _pop(self):
        """
        pop an event from the queue if there is any overdue event otherwise return None
        :return: event or None
        """
        with self._lock:
            if self._event_q:
                event = self._event_q[0]
                now = time.time()
                if event.time <= now:
                    heapq.heappop(self._event_q)
                    return event

    def _push(self, event):
        """
        push event into queue that will be consumed at an absolute time
        :param event: event
        """
        with self._lock:
            heapq.heappush(self._event_q, event)
