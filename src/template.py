import jinja2
import panel as pn


template_string = """
{% extends base %}

<!-- Addition to head -->
{% block postamble %}
<link rel="stylesheet" href="https://stackpath.bootstrapcdn.com/bootstrap/4.3.1/css/bootstrap.min.css">
{% endblock %}

<!-- Addition to body -->
{% block contents %}
{{ app_title }}
<p>This is a Panel app with a custom template allowing us to compose multiple Panel objects into a single HTML document.</p>
<br>
<div class="container">
  <div class="row">
    <div class="col-sm">
      {{ embed(roots.A) }}
    </div>
    <div class="col-sm">
      {{ embed(roots.B) }}
    </div>
  </div>
</div>
{% endblock %}
"""


class BaseTemplate(pn.Template):
    def __init__(self, **kwargs):
        super().__init__(self)
        self.template_string


    def _add_panel(self, panel_string, value):
        self.add_panel(panel_string, value)

    def _add_variable(self, var_string, value):
        self.add_variable(var_string, value)

