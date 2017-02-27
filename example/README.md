## Example

This directory contains examples of sites with tracing implementing using the pyramid_opentracing package. To run the examples, make sure you've installed packages `lightstep` and `opentracing`. If you have a lightstep token and would like to view the created spans, then uncomment the proper lines under the given examples. If you would like to use a different OpenTracing tracer implementation, then you may also replace the lightstep tracer with the tracer of your choice.

Navigate to this directory and then run:

```
> python tween-example.py
```

Open in your browser `localhost:8080/`, `localhost:8080/simple` or `localhost:8080/log`.

To log extra attributes for the Pyramid request object, include them in the configuration:
.. code-block:: python
config.add_settings(opentracing_traced_attributes=['host', 'method', 'other_attribute'])


