def monoid():
    return dict(filters=[], joins=[], parameters=[], human=[])


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


def last_one_wins(values):
    if isinstance(values, basestring):
        return values
    if isinstance(values, (list, tuple)):
        return values[-1]
    return ''


def unpack(x):
    assert isinstance(x, list), 'unknown value: %s' % x
    assert len(x) == 1, "don't know how to merge"
    return x[0]


def lift(prop, f, specs):
    return lambda acc: combine(acc, f, prop, specs)


def combine_specs(specs,
                  filter_fn=None, join_fn=None, param_fn=None, human_fn=None):
    if filter_fn is None:
        filter_fn = unpack
    if join_fn is None:
        join_fn = unique_concat_lists
    if param_fn is None:
        param_fn = concat_lists
    if human_fn is None:
        human_fn = last_one_wins
    return reduce(
        lambda acc, f: f(acc),
        [lift('filters', filter_fn, specs),
         lift('joins', join_fn, specs),
         lift('parameters', param_fn, specs),
         lift('human', human_fn, specs)],
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


def human_and(human):
    return ' and '.join(human)


def human_or(human):
    return ' or '.join(human)


def human_remove_prefix(human):
    # hack to remove the table qualifier from columns
    # this won't be necessary if column queries contain separate
    # fields for table and column
    if not human:
        return ''
    fields = human.split('.', 1)
    if len(fields) == 1:
        return fields[0]
    return fields[1]


def remove_percents(value):
    return value.strip('%')


def combine_filters_and(specs):
    return combine_specs(specs, filter_fn=and_filters, human_fn=human_and)


def combine_filters_or(specs):
    return combine_specs(specs, filter_fn=or_filters, human_fn=human_or)


def simple_filter(operand, column, value, human):
    return dict(filters='%s %s %%s' % (column, operand),
                parameters=[value],
                human=human_remove_prefix(human))


def equal(column, value):
    return simple_filter('=', column, value,
                         '%s is %s' % (column, value))


def notequal(column, value):
    return simple_filter('!=', column, value,
                         '%s is not %s' % (column, value))


def human(value):
    return dict(human=human_remove_prefix(value))


def in_(column, values):
    if not values:
        return {}
    if isinstance(values, basestring):
        return equal(column, values)
    elif len(values) == 1:
        return equal(column, values[0])
    else:
        placeholder_string = ', '.join(['%s'] * len(values))
        human_string = '%s is any of %s' % (column, ', '.join(values))
        return dict(filters='%s IN (%s)' % (column, placeholder_string),
                    parameters=values,
                    human=human_remove_prefix(human_string))


def like(column, value):
    return dict(filters='%s LIKE %%s' % column,
                parameters=[value],
                human=human_remove_prefix(
                    '%s is like %s' % (column, remove_percents(value))))


def vertical(key_column, key_value, value_column, value):
    return combine_specs(
        [combine_filters_and(
            [equal(key_column, key_value),
             in_(value_column, value)]),
         human(in_(value_column, value)['human'])])


def between(column, low, high):
    human_string = '%s is between %s and %s' % (column, low, high)
    return dict(filters='%s BETWEEN %%s AND %%s' % column,
                parameters=[low, high],
                human=human_remove_prefix(human_string))


def join(table, join_spec, join_type='INNER'):
    return dict(
        joins=['%s JOIN %s ON %s' % (join_type, table, join_spec)])


def user_sql(spec):
    # joins is represented as a list of strings, and needs to be combined
    # manually join with core_userfield and phone
    spec = combine_specs([
            spec,
            join('core_userfield cuf', 'cu.id=cuf.parent_id', 'LEFT OUTER'),
            join('core_phone cp', 'cu.id=cp.user_id', 'LEFT OUTER')])
    joins = ' '.join(spec['joins'])
    filters = spec['filters']
    return (('SELECT cu.*, cp.*, cuf.* FROM core_user cu %s WHERE %s' %
             (joins, filters)),
            spec['parameters'])
