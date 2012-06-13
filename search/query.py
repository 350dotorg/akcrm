def monoid(filters=None, joins=None, parameters=None):
    if filters is None:
        filters = []
    if joins is None:
        joins = []
    if parameters is None:
        parameters = []
    return dict(filters=filters,
                joins=joins,
                parameters=parameters,
                )


def evaluate_property(prop, specs):
    values = filter(None, [spec.get(prop) for spec in specs])
    return values


def combine(acc, f, prop, specs):
    values = evaluate_property(prop, specs)
    acc[prop] = f(values)
    return acc


def concat_lists(lists):
    return sum(lists, [])


def unique_concat_lists(lists):
    s = set()
    acc = []
    for l in lists:
        for val in l:
            if val not in s:
                acc.append(val)
                s.add(val)
    return acc


def unpack(x):
    assert isinstance(x, list), 'unknown value: %s' % x
    assert len(x) == 1, "don't know how to merge"
    return x[0]


def lift(prop, f, specs):
    return lambda acc: combine(acc, f, prop, specs)


def combine_specs(specs, filter_fn=None, join_fn=None, param_fn=None):
    if filter_fn is None:
        filter_fn = unpack
    if join_fn is None:
        join_fn = unique_concat_lists
    if param_fn is None:
        param_fn = concat_lists
    return reduce(
        lambda acc, f: f(acc),
        [lift('filters', filter_fn, specs),
         lift('joins', join_fn, specs),
         lift('parameters', param_fn, specs)],
        monoid())


def and_filters(filters):
    filters = [f for f in filters if f]
    return ' AND '.join(filters)


def or_filters(filters):
    if not filters:
        return ''
    filters = [f for f in filters if f]
    if len(filters) == 1:
        return filters[0]
    return '(' + ' OR '.join(filters) + ')'


def combine_filters_and(specs):
    return combine_specs(specs, filter_fn=and_filters)


def combine_filters_or(specs):
    return combine_specs(specs, filter_fn=or_filters)


def simple_filter(operand, column, value):
    return dict(filters='%s %s %%s' % (column, operand),
                parameters=[value])


def equal(column, value):
    return simple_filter('=', column, value)


def notequal(column, value):
    return simple_filter('!=', column, value)


def in_(column, values):
    if not values:
        return {}
    if isinstance(values, basestring):
        return equal(column, values)
    elif len(values) == 1:
        return equal(column, values[0])
    else:
        placeholder_string = ', '.join(['%s'] * len(values))
        return dict(filters='%s IN (%s)' % (column, placeholder_string),
                    parameters=values)


def like(column, value):
    return dict(filters='%s LIKE %%s' % column,
                parameters=[value])


def vertical(key_column, key_value, value_column, value):
    return combine_filters_and(
        [equal(key_column, key_value),
         in_(value_column, value)])


def between(column, low, high):
    return dict(filters='%s BETWEEN %%s AND %%s' % column,
                parameters=[low, high])


def join(table, join_spec, join_type='INNER'):
    return dict(
        joins=['%s JOIN %s ON %s' % (join_type, table, join_spec)])


def user_sql(spec):
    # joins is represented as a list of strings, and needs to be combined
    joins = ' '.join(spec['joins'])
    filters = spec['filters']
    return (('SELECT distinct cu.* FROM core_user cu %s WHERE %s' %
             (joins, filters)),
            spec['parameters'])
