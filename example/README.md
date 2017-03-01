## Example

This directory contains examples of sites with tracing implementing using the pyramid_opentracing package. To run the examples, make sure you've installed packages `lightstep` and `opentracing` (and `waitress` for the clientserver.py one). If you have a lightstep token and would like to view the created spans, then uncomment the proper lines under the given examples. If you would like to use a different OpenTracing tracer implementation, then you may also replace the lightstep tracer with the tracer of your choice.

Navigate to this directory and then run:

```
> python example-file.py
```

For the tween example, open in your browser `localhost:8080/`, `localhost:8080/simple` or `localhost:8080/log`.

For the client-server example, open in your browser `localhost:8080/client/simple`, `localhost:8080/client/log` or `localhost:8080/client/childspan`.

To log extra attributes for the Pyramid request object, include them in the configuration:
.. code-block:: python
config.add_settings(opentracing_traced_attributes=['host', 'method', 'other_attribute'])


