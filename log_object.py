import abc
import sys
import traceback

from django.http import HttpResponseServerError
from django.views import debug

from . import settings


class BaseLogObject(metaclass=abc.ABCMeta):
    def __init__(self, request):
        super().__init__()
        self.request = request

    @abc.abstractproperty
    def to_dict(self):
        raise NotImplementedError

    def format_request(self):
        meta_keys = ['PATH_INFO', 'HTTP_X_SCHEME', 'REMOTE_ADDR',
                     'TZ', 'REMOTE_HOST', 'CONTENT_TYPE', 'CONTENT_LENGTH', 'HTTP_AUTHORIZATION',
                     'HTTP_HOST', 'HTTP_USER_AGENT', 'HTTP_X_FORWARDED_FOR', 'HTTP_X_REAL_IP', ' HTTP_X_REQUEST_ID']
        result = dict(
            method=self.request.method,
            meta={key.lower(): str(value) for key, value in self.request.META.items() if key in meta_keys},
            path=self.request.path_info,
            scheme=self.request.scheme
        )
        try:
            result['data'] = {key: value for key, value in self.request.data.items()}
        except AttributeError:
            if self.request.method == 'GET':
                result['data'] = self.request.GET.dict()
            elif self.request.method == 'POST':
                result['data'] = self.request.POST.dict()

        try:
            result['user'] = str(self.request.user)
        except AttributeError:
            result['user'] = None

        return result


class LogObject(BaseLogObject):
    def __init__(self, request, response):
        super().__init__(request)
        self.response = response

    @property
    def to_dict(self):
        result = dict(
            request=self.format_request(),
            response=self.format_response()
        )
        return result

    def format_response(self):
        result = dict(
            status=self.response.status_code,
            reason=self.response.reason_phrase,
            headers=dict(self.response.items()),
            charset=self.response.charset,
            content=self.response.content.decode(),
        )
        if settings.CONTENT_JSON_ONLY:
            del result['content']

        for field in result.keys():
            if field not in settings.RESPONSE_FIELDS:
                del result[field]
        return result


class ErrorLogObject(BaseLogObject):
    def __init__(self, request, exception):
        super().__init__(request)
        self.exception = exception
        self.__traceback = None

    @property
    def to_dict(self):
        return dict(
            request=self.format_request(),
            exception=self.format_exception()
        )

    @classmethod
    def format_traceback(cls, tb):
        tb = traceback.extract_tb(tb)
        for i in tb:
            yield {'file': i[0], 'line': i[1], 'method': i[2]}

    def format_exception(self):
        result = dict(
            message=str(self.exception),
            traceback=list()
        )
        if sys.version_info[0] == 2:
            _, _, self.__traceback = traceback.sys.exc_info()
        else:
            self.__traceback = traceback.TracebackException.from_exception(self.exception).exc_traceback

        for line in self.format_traceback(self.__traceback):
            result['traceback'].append(line)
        return result

    @property
    def response(self):
        if settings.DEBUG:
            return debug.technical_500_response(self.request, type(self.exception), self.exception, self.__traceback)
        else:
            return HttpResponseServerError(content=b'<h1>Internal Server Error</h1>')

    def __str__(self):
        return 'Traceback (most recent call last):\n{}{}: {}'.format(
            ''.join(traceback.format_tb(self.__traceback)),
            str(type(self.exception)).split('\'')[1], str(self.exception)
        )

